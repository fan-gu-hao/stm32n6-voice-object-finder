#include "finder_kws.h"
#include "finder_kws_compare.h"
#include <stdio.h>
#include "app_config.h"
#include "finder_kws_tables.h"
#include "stai_kws_network.h"
#include "stm32n6xx_hal.h"
#include "ll_aton_osal.h"
#include "ll_aton_caches_interface.h"
#include "arm_math.h"
#include <math.h>
#include <string.h>

_Static_assert(STAI_KWS_NETWORK_IN_NUM == 1, "KWS needs one input");
_Static_assert(STAI_KWS_NETWORK_OUT_NUM == 1, "KWS needs one output");
_Static_assert(STAI_KWS_NETWORK_IN_1_SIZE_BYTES == 49 * 13,
               "Unexpected KWS input size");
_Static_assert(STAI_KWS_NETWORK_IN_1_HEIGHT == 49 &&
               STAI_KWS_NETWORK_IN_1_WIDTH == 13 &&
               STAI_KWS_NETWORK_IN_1_CHANNEL == 1,
               "Unexpected KWS input layout");
_Static_assert(STAI_KWS_NETWORK_OUT_1_SIZE_BYTES == 5,
               "Unexpected KWS output size");
_Static_assert(STAI_KWS_NETWORK_IN_1_FORMAT == STAI_FORMAT_S8,
               "KWS input must be int8");
_Static_assert(STAI_KWS_NETWORK_OUT_1_FORMAT == STAI_FORMAT_S8,
               "KWS output must be int8");

static uint8_t context[STAI_KWS_NETWORK_CONTEXT_SIZE]
  __attribute__((aligned(32)));
static stai_ptr input_ptr, output_ptr;
static const float input_scale[] = STAI_KWS_NETWORK_IN_1_SCALES;
static const int32_t input_zero[] = STAI_KWS_NETWORK_IN_1_OFFSETS;
static const float output_scale[] = STAI_KWS_NETWORK_OUT_1_SCALES;
static const int32_t output_zero[] = STAI_KWS_NETWORK_OUT_1_OFFSETS;
static arm_rfft_fast_instance_f32 fft;

/* 使用靜態緩衝區，避免佔用工作堆疊；限單一推論工作使用。 */
static float frame[512], spectrum[512], power[257], log_mel[40];
static int ready;

/* FINDER_KWS_INPUT_COHERENCY_V1 */
static void kws_begin_input_update(void *ptr, uint32_t size)
{
  /* NPU 快取列為 64 位元組；必須在 CPU 寫入新輸入之前處理。 */
  uintptr_t begin = (uintptr_t)ptr & ~(uintptr_t)63U;
  uintptr_t end = ((uintptr_t)ptr + size + 63U) & ~(uintptr_t)63U;

  LL_ATON_Cache_NPU_Clean_Invalidate_Range(
      begin, (uint32_t)(end - begin));

#if defined(USE_DCACHE)
  /* NPU 寫回後，CPU 也不能沿用同一範圍的舊副本。 */
  SCB_InvalidateDCache_by_Addr(
      (void *)begin, (int32_t)(end - begin));
#endif
  __DSB();
}

static void prepare_input_cache(void *ptr, uint32_t size)
{
#if defined(USE_DCACHE)
  uintptr_t begin = (uintptr_t)ptr & ~(uintptr_t)31;
  uintptr_t end = ((uintptr_t)ptr + size + 31) & ~(uintptr_t)31;
  SCB_CleanInvalidateDCache_by_Addr(
      (void *)begin, (int32_t)(end - begin));
#else
  (void)ptr;
  (void)size;
#endif
}

int finder_kws_init(void)
{
  stai_size count = 1;
  if (ready) return 0;

  /* 核對 N6 模型與訓練匯出的量化參數。 */
  if (fabsf(input_scale[0] - KWS_INPUT_SCALE) > 1e-7f ||
      input_zero[0] != KWS_INPUT_ZERO ||
      fabsf(output_scale[0] - KWS_OUTPUT_SCALE) > 1e-7f ||
      output_zero[0] != KWS_OUTPUT_ZERO) return -1;

  if (arm_rfft_fast_init_512_f32(&fft) != ARM_MATH_SUCCESS) return -2;
  if (stai_kws_network_init(context) != STAI_SUCCESS) return -3;

  if (stai_kws_network_get_inputs(context, &input_ptr, &count) != STAI_SUCCESS ||
      count != 1 || !input_ptr) return -4;

  count = 1;
  if (stai_kws_network_get_outputs(context, &output_ptr, &count) != STAI_SUCCESS ||
      count != 1 || !output_ptr) return -5;

  ready = 1;
  return 0;
}

static void encode_mfcc(const int16_t *pcm, int8_t *dst)
{
  int32_t sum = 0;
  for (unsigned i = 0; i < FINDER_KWS_SAMPLES; ++i)
    sum += pcm[i];
  float mean = (float)sum / (32768.0f * FINDER_KWS_SAMPLES);

  for (unsigned t = 0; t < 49; ++t) {
    /* 30 毫秒窗長、20 毫秒位移，補零到 512 點。 */
    for (unsigned i = 0; i < 480; ++i)
      frame[i] = ((float)pcm[t * 320 + i] / 32768.0f - mean)
                 * kws_window[i];
    memset(frame + 480, 0, 32 * sizeof(float));

    arm_rfft_fast_f32(&fft, frame, spectrum, 0);

    /* 實數傅立葉輸出的第 0、1 元素分別存放直流及奈奎斯特頻率。 */
    power[0] = spectrum[0] * spectrum[0];
    power[256] = spectrum[1] * spectrum[1];
    for (unsigned k = 1; k < 256; ++k)
      power[k] = spectrum[2*k] * spectrum[2*k]
                 + spectrum[2*k+1] * spectrum[2*k+1];

    for (unsigned m = 0; m < 40; ++m) {
      float energy = 0;
      for (unsigned k = 0; k < 257; ++k)
        energy += power[k] * kws_mel[m * 257 + k];
      log_mel[m] = logf(fmaxf(energy, 1e-10f));
    }

    for (unsigned c = 0; c < 13; ++c) {
      float value = 0;
      for (unsigned m = 0; m < 40; ++m)
        value += log_mel[m] * kws_dct[c * 40 + m];

      value = (value - kws_mean[c]) / kws_std[c];
      value = fminf(6.0f, fmaxf(-6.0f, value));

      int32_t q = (int32_t)nearbyintf(value / input_scale[0])
                  + input_zero[0];
      dst[t * 13 + c] =
          (int8_t)(q < -128 ? -128 : q > 127 ? 127 : q);
    }
  }
}


/* FINDER_KWS_COMPARE_V1 */
#if FINDER_KWS_COMPARE_ENABLED
#include "finder_kws_compare_data.h"

_Static_assert(FINDER_KWS_SAMPLES == 16000,
               "Reference PCM size mismatch");
_Static_assert(STAI_KWS_NETWORK_IN_1_SIZE_BYTES == KWS_REF_FEATURES,
               "Reference input size mismatch");
_Static_assert(FINDER_KWS_CLASSES == 5,
               "Reference output size mismatch");

static int cmp_active, cmp_direct;
static unsigned cmp_case, cmp_input_diff, cmp_input_max;

static void compare_encode(const int16_t *pcm, int8_t *dst)
{
  if (cmp_active && cmp_direct)
    memcpy(dst, kws_ref_inputs[cmp_case], KWS_REF_FEATURES);
  else
    encode_mfcc(pcm, dst);

  if (!cmp_active) return;

  cmp_input_diff = cmp_input_max = 0;
  for (unsigned i = 0; i < KWS_REF_FEATURES; i++) {
    int d = (int)dst[i] - kws_ref_inputs[cmp_case][i];
    if (d < 0) d = -d;
    if (d) cmp_input_diff++;
    if ((unsigned)d > cmp_input_max)
      cmp_input_max = (unsigned)d;
  }
}
#endif

/* FINDER_KWS_LIVE_CAPTURE_V1 */
#if FINDER_KWS_LIVE_CAPTURE
static unsigned live_stage;
static int8_t live_input[STAI_KWS_NETWORK_IN_1_SIZE_BYTES];
#endif

int finder_kws_classify(const int16_t *pcm, finder_kws_result_t *result)
{
  if (!ready || !pcm || !result) return -1;

  uint32_t start = HAL_GetTick();
  kws_begin_input_update(input_ptr, STAI_KWS_NETWORK_IN_1_SIZE_BYTES);
#if FINDER_KWS_COMPARE_ENABLED
  compare_encode(pcm, (int8_t *)input_ptr);
#else
  encode_mfcc(pcm, (int8_t *)input_ptr);
#endif
#if FINDER_KWS_LIVE_CAPTURE
  if (live_stage < FINDER_KWS_LIVE_CASES)
    memcpy(live_input, input_ptr, sizeof(live_input));
#endif
  prepare_input_cache(input_ptr, STAI_KWS_NETWORK_IN_1_SIZE_BYTES);
  result->mfcc_ms = HAL_GetTick() - start;

  start = HAL_GetTick();
  stai_return_code status;
  do {
    status = stai_kws_network_run(context, STAI_MODE_ASYNC);
    if (status == STAI_RUNNING_WFE)
      LL_ATON_OSAL_WFE();
  } while (status == STAI_RUNNING_WFE ||
           status == STAI_RUNNING_NO_WFE);

  if (status != STAI_DONE) return -2;
  result->nn_ms = HAL_GetTick() - start;

  /* 本模型最後是 CPU Softmax，直接讀取 CPU 已寫入的輸出。 */
  const int8_t *q = (const int8_t *)output_ptr;
  for (unsigned i = 0; i < FINDER_KWS_CLASSES; ++i)
    result->scores[i] =
        ((int32_t)q[i] - output_zero[0]) * output_scale[0];

  return stai_ext_kws_network_new_inference(context) == STAI_SUCCESS
         ? 0 : -3;
}

#if FINDER_KWS_COMPARE_ENABLED
void finder_kws_compare(void)
{
  printf("CMP,BEGIN\n");
  cmp_active = 1;

  for (unsigned phase = 0; phase < 2; phase++) {
    cmp_direct = (phase == 0);

    for (cmp_case = 0; cmp_case < KWS_REF_COUNT; cmp_case++) {
      finder_kws_result_t result = {0};
      int ret = finder_kws_classify(kws_ref_pcm[cmp_case], &result);

      if (ret != 0) {
        cmp_active = cmp_direct = 0;
        printf("CMP,ERROR,case=%u,code=%d\n", cmp_case, ret);
        return;
      }

      int actual[5];
      unsigned best_pc = 0, best_n6 = 0, max_diff = 0;

      for (unsigned i = 0; i < 5; i++) {
        actual[i] =
            (int)nearbyintf(result.scores[i] / output_scale[0])
            + output_zero[0];

        int d = actual[i] - kws_ref_outputs[cmp_case][i];
        if (d < 0) d = -d;
        if ((unsigned)d > max_diff)
          max_diff = (unsigned)d;

        if (kws_ref_outputs[cmp_case][i]
            > kws_ref_outputs[cmp_case][best_pc])
          best_pc = i;

        if (result.scores[i] > result.scores[best_n6])
          best_n6 = i;
      }

      printf(
          "CMP,case=%s,path=%s,pc=%s,n6=%s,"
          "input_diff=%u,input_max=%u,output_max=%u\n",
          kws_ref_names[cmp_case],
          cmp_direct ? "INPUT" : "PCM",
          kws_ref_names[best_pc], kws_ref_names[best_n6],
          cmp_input_diff, cmp_input_max, max_diff);

      printf(
          "CMP_Q,pc=%d,%d,%d,%d,%d,n6=%d,%d,%d,%d,%d\n",
          kws_ref_outputs[cmp_case][0],
          kws_ref_outputs[cmp_case][1],
          kws_ref_outputs[cmp_case][2],
          kws_ref_outputs[cmp_case][3],
          kws_ref_outputs[cmp_case][4],
          actual[0], actual[1], actual[2], actual[3], actual[4]);
    }
  }

  cmp_active = cmp_direct = 0;
  printf("CMP,END\n");
}
#endif

#if FINDER_KWS_LIVE_CAPTURE
_Static_assert(FINDER_KWS_SAMPLES == 16000, "Live PCM size mismatch");
_Static_assert(STAI_KWS_NETWORK_IN_1_SIZE_BYTES == 637, "Live input mismatch");
_Static_assert(FINDER_KWS_CLASSES == 5, "Live output mismatch");

static int16_t live_pcm[16000];
static int8_t live_features[637], live_output[5];
static const char *const live_labels[] = {
  "cup", "bottle", "phone", "silence",
  "bottle", "phone", "cup", "unknown",
  "phone", "cup", "bottle", "silence",
  "cup", "bottle", "phone", "unknown",
  "bottle", "phone", "cup", "silence",
  "phone", "cup", "bottle", "unknown",
  "cup", "bottle", "phone", "silence",
  "bottle", "phone", "cup", "unknown",
  "cup", "bottle", "phone", "silence",
  "bottle", "phone", "cup", "unknown",
  "phone", "cup", "bottle", "silence",
  "cup", "bottle", "phone", "unknown"
};

static uint32_t live_send(uint32_t offset, const void *data,
                          uint32_t length, uint32_t crc)
{
  const uint8_t *p = data;
  const char hex[] = "0123456789abcdef";
  char line[257];

  for (uint32_t base = 0; base < length; base += 128U) {
    uint32_t n = length - base;
    if (n > 128U) n = 128U;

    for (uint32_t i = 0; i < n; i++) {
      uint8_t b = p[base + i];
      line[2U*i] = hex[b >> 4];
      line[2U*i+1U] = hex[b & 15U];
      crc ^= b;
      for (unsigned j = 0; j < 8; j++)
        crc = (crc >> 1) ^ ((crc & 1U) ? 0xEDB88320U : 0U);
    }

    line[2U*n] = 0;
    printf("LIVE,D,%lu,%s\n", (unsigned long)(offset + base), line);
  }
  return crc;
}

void finder_kws_live_capture(const int16_t *pcm,
                             const finder_kws_result_t *result)
{
  static int started, selected, saved_peak;
  static uint32_t start, saved_ms;
  static uint64_t best_energy;

  if (live_stage >= FINDER_KWS_LIVE_CASES) return;

  uint32_t now = HAL_GetTick();
  if (!started) {
    start = now;
    selected = 0;
    best_energy = 0;
    started = 1;
    printf("LIVE,CUE,%u,%s\n", live_stage, live_labels[live_stage]);
    return;
  }

  uint32_t elapsed = now - start;
  if (elapsed < 1000U) return;

  if (elapsed >= 4500U) {
    if (!selected) {
      printf("LIVE,ERROR,no_sample\n");
      live_stage = FINDER_KWS_LIVE_CASES;
      return;
    }

    printf("LIVE,B,%u,%s,%lu,%d\n", live_stage,
           live_labels[live_stage], (unsigned long)saved_ms, saved_peak);

    uint32_t crc = live_send(0, live_pcm, sizeof(live_pcm), ~0U);
    crc = live_send(32000, live_features, sizeof(live_features), crc);
    crc = live_send(32637, live_output, sizeof(live_output), crc);
    printf("LIVE,E,%08lx\n", (unsigned long)~crc);

    live_stage++;
    started = 0;
    if (live_stage == FINDER_KWS_LIVE_CASES) printf("LIVE,DONE\n");
    return;
  }

  int64_t sum = 0;
  uint64_t squares = 0;
  int peak = 0;
  for (unsigned i = 0; i < 16000; i++) {
    int32_t v = pcm[i];
    sum += v;
    squares += (uint64_t)((int64_t)v * v);
    if (v < 0) v = -v;
    if (v > peak) peak = v;
  }

  uint64_t energy = squares - (uint64_t)(sum * sum) / 16000U;

  /* FINDER_KWS_COLLECT_V1: 按音訊能量選窗。 */
  if (!selected || energy > best_energy) {
    selected = 1;
    best_energy = energy;
    saved_ms = elapsed;
    saved_peak = peak;
    memcpy(live_pcm, pcm, sizeof(live_pcm));
    memcpy(live_features, live_input, sizeof(live_features));

    for (unsigned i = 0; i < 5; i++)
      live_output[i] = (int8_t)((int)nearbyintf(
          result->scores[i] / output_scale[0]) + output_zero[0]);
  }
}
#endif
