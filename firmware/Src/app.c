/**
  ******************************************************************************
  * @file    app.c
  * @author  MDG Application Team
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2024 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */

/* FINDER_VISION_APP_V2 */

#include "app.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "app_cam.h"
#include "app_config.h"
#include "finder.h"
#include "finder_kws.h"
#include "finder_kws_compare.h"
#include "finder_mic.h"
#include "app_postprocess.h"
#include "stai_network.h"
#include "ll_aton_osal.h"
#include "cmw_camera.h"
#include "scrl.h"
#include "stm32n6570_discovery.h"
#include "stm32_lcd.h"
#include "stm32_lcd_ex.h"
#include "stm32n6xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "utils.h"

#define FREERTOS_PRIORITY(p) ((UBaseType_t)((int)tskIDLE_PRIORITY + configMAX_PRIORITIES / 2 + (p)))
#define LCD_FG_WIDTH LCD_BG_WIDTH
#define LCD_FG_HEIGHT LCD_BG_HEIGHT
#define DISPLAY_BUFFER_NB (DISPLAY_DELAY + 2)
#define BQUEUE_MAX_BUFFERS 2
#define LCD_FONT Font20
#define UTIL_LCD_COLOR_TRANSPARENT 0
#define FINDER_CONFIRM_FRAMES 2U
#define FINDER_CONFIRM_IOU (0.30f)
#define MASK_BYTES (AI_YOLOV8_SEG_PP_MASK_SIZE * AI_YOLOV8_SEG_PP_MASK_SIZE)
#define CACHE_OP(op) do { if (is_cache_enable()) { op; } } while (0)

_Static_assert(STAI_NETWORK_IN_NUM == 1, "Expected one camera input");
_Static_assert(STAI_NETWORK_IN_1_WIDTH == 256 &&
               STAI_NETWORK_IN_1_HEIGHT == 256, "Expected 256x256 input");
_Static_assert(STAI_NETWORK_IN_1_CHANNEL == 3 &&
               STAI_NETWORK_IN_1_FORMAT == STAI_FORMAT_U8, "Expected RGB uint8");
_Static_assert(STAI_NETWORK_OUT_NUM == 2, "Expected two YOLO outputs");
_Static_assert(STAI_NETWORK_OUT_1_FORMAT == STAI_FORMAT_S8 &&
               STAI_NETWORK_OUT_2_FORMAT == STAI_FORMAT_S8, "Expected int8 outputs");

typedef struct {
  uint32_t X0, Y0, XSize, YSize;
} Rectangle_TypeDef;

typedef struct {
  SemaphoreHandle_t free;
  StaticSemaphore_t free_buffer;
  SemaphoreHandle_t ready;
  StaticSemaphore_t ready_buffer;
  int buffer_nb;
  uint8_t *buffers[BQUEUE_MAX_BUFFERS];
  int free_idx, ready_idx;
} bqueue_t;

typedef struct {
  unsigned target;
  uint32_t generation;
  int found;
  uint32_t nn_ms, pp_ms, period_ms;
  int voice_class;
  unsigned voice_score;
  uint32_t voice_mfcc_ms, voice_nn_ms;
  iseg_pp_outBuffer_t box;
} display_info_t;

typedef struct {
  SemaphoreHandle_t update;
  StaticSemaphore_t update_buffer;
  SemaphoreHandle_t lock;
  StaticSemaphore_t lock_buffer;
  display_info_t info;
} display_t;

typedef struct {
  stai_network_info network_info;
  stai_ptr nn_in;
  stai_ptr nn_out[STAI_NETWORK_OUT_NUM];
  iseg_yolov8_pp_static_param_t static_param;
  iseg_pp_out_t output;
} yolo_model_info_t;

static const int target_classes[FINDER_TARGET_COUNT] = {41, 39, 67};
static const char *const target_names[FINDER_TARGET_COUNT] = {"CUP", "BOTTLE", "PHONE"};
static Rectangle_TypeDef lcd_bg_area = {0, 0, LCD_BG_WIDTH, LCD_BG_HEIGHT};
static Rectangle_TypeDef lcd_fg_area = {0, 0, LCD_FG_WIDTH, LCD_FG_HEIGHT};

static uint8_t lcd_bg_buffer[DISPLAY_BUFFER_NB][LCD_BG_WIDTH * LCD_BG_HEIGHT * DISPLAY_BPP] ALIGN_32 IN_PSRAM;
static int lcd_bg_buffer_disp_idx = 1;
static int lcd_bg_buffer_capt_idx;
static uint8_t lcd_fg_buffer[2][LCD_FG_WIDTH * LCD_FG_HEIGHT * 2] ALIGN_32 IN_PSRAM;
static int lcd_fg_buffer_rd_idx;
static uint8_t screen_buffer[LCD_BG_WIDTH * LCD_BG_HEIGHT * 2] ALIGN_32 IN_PSRAM;
static display_t disp;

/* 複製遮罩，避免下一次推論改寫顯示中的結果。 */
static uint8_t result_mask[MASK_BYTES] ALIGN_32 IN_PSRAM;
static uint8_t drawing_mask[MASK_BYTES] ALIGN_32 IN_PSRAM;

static uint8_t network_ctx[STAI_NETWORK_CONTEXT_SIZE] ALIGN_32;
static uint8_t nn_input_buffers[2][STAI_NETWORK_IN_1_SIZE_BYTES] ALIGN_32 IN_PSRAM;
static bqueue_t nn_input_queue;
static yolo_model_info_t yolo_info;

static StaticTask_t nn_thread, dp_thread, isp_thread;
static StackType_t nn_thread_stack[2 * configMINIMAL_STACK_SIZE];
static StackType_t dp_thread_stack[2 * configMINIMAL_STACK_SIZE];
static StackType_t isp_thread_stack[2 * configMINIMAL_STACK_SIZE];
static SemaphoreHandle_t isp_sem;
static StaticSemaphore_t isp_sem_buffer;

static int is_cache_enable()
{
#if defined(USE_DCACHE)
  return 1;
#else
  return 0;
#endif
}

static int bqueue_init(bqueue_t *bq, int buffer_nb, uint8_t **buffers)
{
  int i;

  if (buffer_nb > BQUEUE_MAX_BUFFERS)
    return -1;

  bq->free = xSemaphoreCreateCountingStatic(buffer_nb, buffer_nb, &bq->free_buffer);
  if (!bq->free)
    goto free_sem_error;
  bq->ready = xSemaphoreCreateCountingStatic(buffer_nb, 0, &bq->ready_buffer);
  if (!bq->ready)
    goto ready_sem_error;

  bq->buffer_nb = buffer_nb;
  for (i = 0; i < buffer_nb; i++) {
    assert(buffers[i]);
    bq->buffers[i] = buffers[i];
  }
  bq->free_idx = 0;
  bq->ready_idx = 0;

  return 0;

ready_sem_error:
  vSemaphoreDelete(bq->free);
free_sem_error:
  return -1;
}

static uint8_t *bqueue_get_free(bqueue_t *bq, int is_blocking)
{
  uint8_t *res;
  int ret;

  if (xPortIsInsideInterrupt()) {
    BaseType_t woken = pdFALSE;
    ret = xSemaphoreTakeFromISR(bq->free, &woken);
    portYIELD_FROM_ISR(woken);
  } else {
    ret = xSemaphoreTake(bq->free, is_blocking ? portMAX_DELAY : 0);
  }
  if (ret == pdFALSE)
    return NULL;

  res = bq->buffers[bq->free_idx];
  bq->free_idx = (bq->free_idx + 1) % bq->buffer_nb;

  return res;
}

static void bqueue_put_free(bqueue_t *bq)
{
  int ret;

  ret = xSemaphoreGive(bq->free);
  assert(ret == pdTRUE);
}

static uint8_t *bqueue_get_ready(bqueue_t *bq)
{
  uint8_t *res;
  int ret;

  ret = xSemaphoreTake(bq->ready, portMAX_DELAY);
  assert(ret == pdTRUE);

  res = bq->buffers[bq->ready_idx];
  bq->ready_idx = (bq->ready_idx + 1) % bq->buffer_nb;

  return res;
}

static void bqueue_put_ready(bqueue_t *bq)
{
  BaseType_t xHigherPriorityTaskWoken = pdFALSE;
  int ret;

  if (xPortIsInsideInterrupt()) {
    ret = xSemaphoreGiveFromISR(bq->ready, &xHigherPriorityTaskWoken);
    assert(ret == pdTRUE);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
  } else {
    ret = xSemaphoreGive(bq->ready);
    assert(ret == pdTRUE);
  }
}

static void reload_bg_layer(int next_disp_idx)
{
  int ret;

  ret = SCRL_SetAddress_NoReload(lcd_bg_buffer[next_disp_idx], SCRL_LAYER_0);
  assert(ret == 0);
  ret = SCRL_ReloadLayer(SCRL_LAYER_0);
  assert(ret == 0);

  ret = SRCL_Update();
  assert(ret == 0);
}

static void app_main_pipe_frame_event()
{
  int next_disp_idx = (lcd_bg_buffer_disp_idx + 1) % DISPLAY_BUFFER_NB;
  int next_capt_idx = (lcd_bg_buffer_capt_idx + 1) % DISPLAY_BUFFER_NB;
  int ret;

  ret = HAL_DCMIPP_PIPE_SetMemoryAddress(CMW_CAMERA_GetDCMIPPHandle(), DCMIPP_PIPE1,
                                         DCMIPP_MEMORY_ADDRESS_0, (uint32_t) lcd_bg_buffer[next_capt_idx]);
  assert(ret == HAL_OK);

  reload_bg_layer(next_disp_idx);
  lcd_bg_buffer_disp_idx = next_disp_idx;
  lcd_bg_buffer_capt_idx = next_capt_idx;

}


static void app_ancillary_pipe_frame_event()
{
  uint8_t *next_buffer;
  int ret;

  next_buffer = bqueue_get_free(&nn_input_queue, 0);
  if (next_buffer) {
    ret = HAL_DCMIPP_PIPE_SetMemoryAddress(CMW_CAMERA_GetDCMIPPHandle(), DCMIPP_PIPE2,
                                           DCMIPP_MEMORY_ADDRESS_0, (uint32_t) next_buffer);
    assert(ret == HAL_OK);
    bqueue_put_ready(&nn_input_queue);
  }
}

static void app_main_pipe_vsync_event()
{
  BaseType_t xHigherPriorityTaskWoken = pdFALSE;
  int ret;

  ret = xSemaphoreGiveFromISR(isp_sem, &xHigherPriorityTaskWoken);
  if (ret == pdTRUE)
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}


int finder_select_target(finder_target_t target)
{
  if ((unsigned)target >= FINDER_TARGET_COUNT || !disp.lock)
    return -1;

  int ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
  assert(ret == pdTRUE);
  disp.info.target = target;
  disp.info.generation++;
  disp.info.found = 0;
  ret = xSemaphoreGive(disp.lock);
  assert(ret == pdTRUE);
  xSemaphoreGive(disp.update);
  return 0;
}

static float box_iou(const iseg_pp_outBuffer_t *a, const iseg_pp_outBuffer_t *b)
{
  float left = fmaxf(a->x_center - a->width * .5f, b->x_center - b->width * .5f);
  float right = fminf(a->x_center + a->width * .5f, b->x_center + b->width * .5f);
  float top = fmaxf(a->y_center - a->height * .5f, b->y_center - b->height * .5f);
  float bottom = fminf(a->y_center + a->height * .5f, b->y_center + b->height * .5f);
  float intersection = fmaxf(0, right - left) * fmaxf(0, bottom - top);
  float area = a->width * a->height + b->width * b->height - intersection;
  return area > 0 ? intersection / area : 0;
}

static void run_yolo(void)
{
  stai_return_code ret;
  do {
    ret = stai_network_run(network_ctx, STAI_MODE_ASYNC);
    if (ret == STAI_RUNNING_WFE)
      LL_ATON_OSAL_WFE();
  } while (ret == STAI_RUNNING_WFE || ret == STAI_RUNNING_NO_WFE);

  assert(ret == STAI_DONE);
  ret = stai_ext_network_new_inference(network_ctx);
  assert(ret == STAI_SUCCESS);
}


/* FINDER_VOICE_LIVE_V1 */
static int voice_online;
static int16_t voice_pcm[FINDER_KWS_SAMPLES];
static const char *const voice_names[] = {
  "CUP", "BOTTLE", "PHONE", "UNKNOWN", "SILENCE"
};

/* FINDER_VOICE_ACCEPT_V2 */
/* 起始音量門檻：本輪安靜峰值 1748，三個單字峰值均超過 8800。 */
#define FINDER_VOICE_MIN_PEAK 2500

static void finder_voice_poll(void)
{
  static int candidate = -1;
  static unsigned hits, quiet_windows;
  static int armed = 1;
  static uint32_t last_command, last_print;

  if (!voice_online) return;

  int ret = finder_mic_take(voice_pcm);
  if (ret == 0) return;
  if (ret < 0) goto voice_error;
  /* FINDER_KWS_COLLECT_V1 */
#if FINDER_KWS_LIVE_CAPTURE
  finder_kws_result_t captured;
  ret = finder_kws_classify(voice_pcm, &captured);
  if (ret != 0) goto voice_error;
  finder_kws_live_capture(voice_pcm, &captured);
  return;
#endif

  /* FINDER_VOICE_TRACE_V1 */
  unsigned clipped = 0;
  int peak = 0;
  for (unsigned i = 0; i < FINDER_KWS_SAMPLES; i++) {
    int value = voice_pcm[i];
    if (value == 32767 || value == -32768) clipped++;
    if (value < 0) value = -value;
    if (value > peak) peak = value;
  }

  uint32_t now = HAL_GetTick();

  /* 小音量不進行命令辨識；連續兩個安靜視窗後重新接受命令。 */
  if (peak < FINDER_VOICE_MIN_PEAK) {
    hits = 0;
    candidate = -1;

    if (quiet_windows < 2U) quiet_windows++;
    if (quiet_windows >= 2U) armed = 1;

    if (now - last_print >= 1000U) {
      printf("VOICE,state=QUIET,peak=%d\n", peak);
      last_print = now;
    }
    return;
  }

  quiet_windows = 0;

  /* 同一段持續發音，最多接受一次命令。 */
  if (!armed) {
    if (now - last_print >= 1000U) {
      printf("VOICE,state=WAIT_QUIET,peak=%d\n", peak);
      last_print = now;
    }
    return;
  }

  finder_kws_result_t result;
  ret = finder_kws_classify(voice_pcm, &result);
  if (ret != 0) goto voice_error;

  unsigned best = 0;
  for (unsigned i = 1; i < FINDER_KWS_CLASSES; i++)
    if (result.scores[i] > result.scores[best]) best = i;

  float second = 0;
  for (unsigned i = 0; i < FINDER_KWS_CLASSES; i++)
    if (i != best && result.scores[i] > second)
      second = result.scores[i];

  float score = result.scores[best];

  if (best < FINDER_TARGET_COUNT &&
      score >= 0.90f && score - second >= 0.25f) {
    hits = candidate == (int)best ? hits + 1U : 1U;
    candidate = (int)best;
  } else {
    hits = 0;
    candidate = -1;
  }

  unsigned percent = (unsigned)(score * 100.0f + 0.5f);
  unsigned trace_hits = hits;
  int accepted = 0;
  now = HAL_GetTick();

  if (hits >= 2U && now - last_command >= 1200U) {
    ret = finder_select_target((finder_target_t)best);
    assert(ret == 0);

    accepted = 1;
    last_command = now;
    hits = 0;
    candidate = -1;
    armed = 0;

    /* 畫面保留最後接受的命令。 */
    xSemaphoreTake(disp.lock, portMAX_DELAY);
    disp.info.voice_class = (int)best;
    disp.info.voice_score = percent;
    disp.info.voice_mfcc_ms = result.mfcc_ms;
    disp.info.voice_nn_ms = result.nn_ms;
    xSemaphoreGive(disp.lock);
    xSemaphoreGive(disp.update);
  }

  /* 接受命令立即列印，其餘候選結果最多每秒列印一次。 */
  {
    unsigned p[FINDER_KWS_CLASSES];
    for (unsigned i = 0; i < FINDER_KWS_CLASSES; ++i)
      p[i] = (unsigned)(result.scores[i] * 100.0f + 0.5f);
    printf("KWS,class=%s,score=%u,accept=%d,peak=%d,clip=%u,hits=%u,"
           "cup=%u,bottle=%u,phone=%u,unknown=%u,silence=%u,"
           "gap=%u,t=%lu\n",
           voice_names[best], percent, accepted, peak, clipped, trace_hits,
           p[0], p[1], p[2], p[3], p[4],
           (unsigned)((score - second) * 100.0f + 0.5f),
           (unsigned long)now);
    last_print = now;
  }
  return;

voice_error:
  printf("VOICE,error=%d,mic=0x%08lx\n",
         ret, (unsigned long)finder_mic_error());

  voice_online = 0;
  xSemaphoreTake(disp.lock, portMAX_DELAY);
  disp.info.voice_class = -2;
  xSemaphoreGive(disp.lock);
  xSemaphoreGive(disp.update);
}


static void nn_thread_fct(void *arg)
{
  (void)arg;
  stai_network_info *info = &yolo_info.network_info;
  stai_ptr *outputs = yolo_info.nn_out;
  stai_size input_count = 1, output_count = STAI_NETWORK_OUT_NUM;
  iseg_pp_outBuffer_t previous = {0};
  unsigned hits = 0;
  uint32_t previous_generation = UINT32_MAX;
  uint32_t last_start = 0, last_log = 0;

  int ret = stai_runtime_init();
  assert(ret == STAI_SUCCESS);
  ret = stai_network_init(network_ctx);
  assert(ret == STAI_SUCCESS);
  ret = stai_network_get_info(network_ctx, info);
  assert(ret == STAI_SUCCESS);
  assert(info->n_inputs == 1 && info->n_outputs == STAI_NETWORK_OUT_NUM);
  assert(info->inputs[0].size_bytes == sizeof(nn_input_buffers[0]));

  ret = stai_network_get_inputs(network_ctx, &yolo_info.nn_in, &input_count);
  assert(ret == STAI_SUCCESS && yolo_info.nn_in && input_count == 1);
  ret = stai_network_get_outputs(network_ctx, outputs, &output_count);
  assert(ret == STAI_SUCCESS && output_count == STAI_NETWORK_OUT_NUM);
  ret = app_postprocess_init(&yolo_info.static_param, info);
  assert(ret == 0);
  /* FINDER_KWS_CORE_V1 */
  ret = finder_kws_init();
  printf("KWS initialization: %d\n", ret);
  assert(ret == 0);
  /* FINDER_KWS_COMPARE_V1 */
#if FINDER_KWS_COMPARE_ENABLED
  finder_kws_compare();
#endif
  ret = finder_mic_start();
  printf("Microphone initialization: %d\n", ret);
  voice_online = (ret == 0);

  xSemaphoreTake(disp.lock, portMAX_DELAY);
  disp.info.voice_class = voice_online ? -1 : -2;
  xSemaphoreGive(disp.lock);


  CACHE_OP(SCB_CleanInvalidateDCache_by_Addr(nn_input_buffers, sizeof(nn_input_buffers)));
  uint8_t *first = bqueue_get_free(&nn_input_queue, 0);
  assert(first);
  printf("Finder: YOLO ready; USER1 selects CUP / BOTTLE / PHONE\n");
  CAM_NNPipe_Start(first, CMW_MODE_CONTINUOUS);

  while (1) {
    finder_voice_poll();
    uint8_t *capture = bqueue_get_ready(&nn_input_queue);
    assert(capture);
    uint32_t start = HAL_GetTick();
    uint32_t period = last_start ? start - last_start : 0;
    last_start = start;

    ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
    assert(ret == pdTRUE);
    unsigned target = disp.info.target;
    uint32_t generation = disp.info.generation;
    ret = xSemaphoreGive(disp.lock);
    assert(ret == pdTRUE);

    /* 複製到模型產碼所配置的輸入區，完成後歸還攝影機緩衝區。 */
    CACHE_OP(SCB_InvalidateDCache_by_Addr(capture, sizeof(nn_input_buffers[0])));
    memcpy(yolo_info.nn_in, capture, sizeof(nn_input_buffers[0]));
    CACHE_OP(SCB_CleanInvalidateDCache_by_Addr(yolo_info.nn_in, info->inputs[0].size_bytes));
    bqueue_put_free(&nn_input_queue);

    uint32_t ts = HAL_GetTick();
    run_yolo();
    uint32_t nn_ms = HAL_GetTick() - ts;

    for (unsigned i = 0; i < output_count; i++)
      CACHE_OP(SCB_InvalidateDCache_by_Addr(outputs[i], info->outputs[i].size_bytes));

    ts = HAL_GetTick();
    ret = app_postprocess_run((void **)outputs, output_count,
                             &yolo_info.output, &yolo_info.static_param);
    assert(ret == 0);
    uint32_t pp_ms = HAL_GetTick() - ts;

    /* 從原本的 80 類辨識結果中篩選指定物件。 */
    iseg_pp_outBuffer_t *best = NULL;
    for (int i = 0; i < yolo_info.output.nb_detect; i++) {
      iseg_pp_outBuffer_t *box = &yolo_info.output.pOutBuff[i];
      if (box->class_index == target_classes[target] &&
          box->conf >= AI_YOLOV8_SEG_PP_CONF_THRESHOLD &&
          (!best || box->conf > best->conf))
        best = box;
    }

    if (generation != previous_generation) {
      hits = 0;
      previous_generation = generation;
    }
    if (!best) {
      hits = 0;
    } else {
      hits = hits && box_iou(best, &previous) >= FINDER_CONFIRM_IOU ? hits + 1 : 1;
      hits = MIN(hits, FINDER_CONFIRM_FRAMES);
      previous = *best;
      previous.pMask = NULL;
    }

    int found = best && hits >= FINDER_CONFIRM_FRAMES;
    ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
    assert(ret == pdTRUE);

    /* 若推論途中切換目標，捨棄舊目標的結果。 */
    if (generation == disp.info.generation) {
      disp.info.found = found;
      disp.info.nn_ms = nn_ms;
      disp.info.pp_ms = pp_ms;
      disp.info.period_ms = period;
      if (found) {
        disp.info.box = *best;
        disp.info.box.pMask = NULL;
        memcpy(result_mask, best->pMask, MASK_BYTES);
      }
    }

    ret = xSemaphoreGive(disp.lock);
    assert(ret == pdTRUE);
    xSemaphoreGive(disp.update);

    for (unsigned i = 0; i < output_count; i++)
      CACHE_OP(SCB_InvalidateDCache_by_Addr(outputs[i], info->outputs[i].size_bytes));

    if (HAL_GetTick() - last_log >= 1000) {
      last_log = HAL_GetTick();
      printf("FINDER,target=%s,found=%d,score=%u,nn_ms=%lu,pp_ms=%lu\n",
             target_names[target], found, found ? (unsigned)(best->conf * 100) : 0,
             (unsigned long)nn_ms, (unsigned long)pp_ms);
    }
  }
}

static int clamp_coord(int value, int low, int high)
{
  return MAX(low, MIN(high, value));
}

static void Display_NetworkOutput(const display_info_t *info)
{
  const int side = LCD_BG_HEIGHT;
  const int left = (LCD_BG_WIDTH - side) / 2;

  UTIL_LCD_Clear(UTIL_LCD_COLOR_TRANSPARENT);
  UTIL_LCD_DrawRect(left, 0, side - 1, side - 1, UTIL_LCD_COLOR_WHITE);

  if (info->found) {
    const iseg_pp_outBuffer_t *b = &info->box;
    int x0 = left + clamp_coord((int)((b->x_center - b->width / 2) * side), 0, side - 1);
    int y0 = clamp_coord((int)((b->y_center - b->height / 2) * side), 0, side - 1);
    int x1 = left + clamp_coord((int)((b->x_center + b->width / 2) * side), 0, side - 1);
    int y1 = clamp_coord((int)((b->y_center + b->height / 2) * side), 0, side - 1);

    for (int y = 0; y < AI_YOLOV8_SEG_PP_MASK_SIZE; y++) {
      for (int x = 0; x < AI_YOLOV8_SEG_PP_MASK_SIZE; x++) {
        if (!drawing_mask[y * AI_YOLOV8_SEG_PP_MASK_SIZE + x])
          continue;

        int mx0 = MAX(x0, left + x * side / AI_YOLOV8_SEG_PP_MASK_SIZE);
        int my0 = MAX(y0, y * side / AI_YOLOV8_SEG_PP_MASK_SIZE);
        int mx1 = MIN(x1 + 1, left + (x + 1) * side / AI_YOLOV8_SEG_PP_MASK_SIZE);
        int my1 = MIN(y1 + 1, (y + 1) * side / AI_YOLOV8_SEG_PP_MASK_SIZE);

        if (mx1 > mx0 && my1 > my0)
          UTIL_LCD_FillRect(mx0, my0, mx1 - mx0, my1 - my0, 0x6000FF00);
      }
    }

    if (x1 > x0 && y1 > y0)
      UTIL_LCD_DrawRect(x0, y0, x1 - x0, y1 - y0, UTIL_LCD_COLOR_GREEN);
  }

  UTIL_LCD_SetBackColor(0xC0000000);
  UTIL_LCD_SetTextColor(UTIL_LCD_COLOR_WHITE);
  UTIL_LCDEx_PrintfAt(0, LINE(0), CENTER_MODE, "Voice Object Finder");
  UTIL_LCDEx_PrintfAt(0, LINE(1), CENTER_MODE, "Target: %s  %s  Score: %u%%",
                     target_names[info->target], info->found ? "FOUND" : "SEARCHING",
                     info->found ? (unsigned)(info->box.conf * 100) : 0);
  UTIL_LCDEx_PrintfAt(0, LINE(17), CENTER_MODE, "Say: cup / bottle / phone");
  if (info->voice_class < 0)
    UTIL_LCDEx_PrintfAt(
        0, LINE(18), CENTER_MODE,
        "Voice: %s | USER1: change target",
        info->voice_class == -2 ? "ERROR" : "LISTENING");
  else
    UTIL_LCDEx_PrintfAt(
        0, LINE(18), CENTER_MODE,
        "Voice: %s %u%% | USER1: change target",
        voice_names[info->voice_class], info->voice_score);
  UTIL_LCDEx_PrintfAt(0, LINE(19), CENTER_MODE, "NN: %lu ms  PP: %lu ms  Update: %lu ms",
                     (unsigned long)info->nn_ms, (unsigned long)info->pp_ms,
                     (unsigned long)info->period_ms);
  UTIL_LCD_SetBackColor(0);
}

static void dp_update_drawing_area()
{
  int ret;

  __disable_irq();
  ret = SCRL_SetAddress_NoReload(lcd_fg_buffer[lcd_fg_buffer_rd_idx], SCRL_LAYER_1);
  assert(ret == HAL_OK);
  __enable_irq();
}

static void dp_commit_drawing_area()
{
  int ret;

  __disable_irq();
  ret = SCRL_ReloadLayer(SCRL_LAYER_1);
  assert(ret == HAL_OK);
  __enable_irq();
  lcd_fg_buffer_rd_idx = 1 - lcd_fg_buffer_rd_idx;
}


static void dp_thread_fct(void *arg)
{
  (void)arg;
  display_info_t info;
  int ret = BSP_PB_Init(BUTTON_USER1, BUTTON_MODE_GPIO);
  assert(ret == BSP_ERROR_NONE);
  int previous_button = BSP_PB_GetState(BUTTON_USER1);
  uint32_t last_button = HAL_GetTick();

  while (1) {
    xSemaphoreTake(disp.update, pdMS_TO_TICKS(100));
    int button = BSP_PB_GetState(BUTTON_USER1);

    if (button && !previous_button && HAL_GetTick() - last_button >= 200) {
      ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
      assert(ret == pdTRUE);
      unsigned next = (disp.info.target + 1) % FINDER_TARGET_COUNT;
      ret = xSemaphoreGive(disp.lock);
      assert(ret == pdTRUE);
      finder_select_target((finder_target_t)next);
      last_button = HAL_GetTick();
    }
    previous_button = button;

    ret = xSemaphoreTake(disp.lock, portMAX_DELAY);
    assert(ret == pdTRUE);
    info = disp.info;
    if (info.found)
      memcpy(drawing_mask, result_mask, MASK_BYTES);
    ret = xSemaphoreGive(disp.lock);
    assert(ret == pdTRUE);

    dp_update_drawing_area();
    Display_NetworkOutput(&info);
    CACHE_OP(SCB_CleanDCache_by_Addr(lcd_fg_buffer[lcd_fg_buffer_rd_idx],
                                    sizeof(lcd_fg_buffer[0])));
    dp_commit_drawing_area();
  }
}

static void isp_thread_fct(void *arg)
{
  int ret;

  while (1) {
    ret = xSemaphoreTake(isp_sem, portMAX_DELAY);
    assert(ret == pdTRUE);

    CAM_IspUpdate();
  }
}

static void Display_init()
{
  SCRL_LayerConfig layers_config[2] = {
    {
      .origin = {lcd_bg_area.X0, lcd_bg_area.Y0},
      .size = {lcd_bg_area.XSize, lcd_bg_area.YSize},
#if HAS_ROTATION_SUPPORT == 0
      .format = SCRL_RGB888,
#else
      .format = SCRL_ARGB8888,
#endif
      .address = lcd_bg_buffer[lcd_bg_buffer_disp_idx],
    },
    {
      .origin = {lcd_fg_area.X0, lcd_fg_area.Y0},
      .size = {lcd_fg_area.XSize, lcd_fg_area.YSize},
      .format = SCRL_ARGB4444,
      .address = lcd_fg_buffer[1],
    },
  };
  SCRL_ScreenConfig screen_config = {
    .size = {lcd_bg_area.XSize, lcd_bg_area.YSize},
#ifdef SCR_LIB_USE_SPI
    .format = SCRL_RGB565,
#else
     .format = SCRL_YUV422, /* Use SCRL_RGB565 if host support this format to reduce cpu load */
#endif
    .address = screen_buffer,
    .fps = CAMERA_FPS,
  };
  int ret;

  ret = SCRL_Init((SCRL_LayerConfig *[2]){&layers_config[0], &layers_config[1]}, &screen_config);
  assert(ret == 0);

  UTIL_LCD_SetLayer(SCRL_LAYER_1);
  UTIL_LCD_Clear(UTIL_LCD_COLOR_TRANSPARENT);
  UTIL_LCD_SetFont(&LCD_FONT);
  UTIL_LCD_SetTextColor(UTIL_LCD_COLOR_WHITE);
}

void app_run()
{
  UBaseType_t isp_priority = FREERTOS_PRIORITY(2);
  UBaseType_t dp_priority = FREERTOS_PRIORITY(-2);
  UBaseType_t nn_priority = FREERTOS_PRIORITY(1);
  TaskHandle_t hdl;
  int ret;

  printf("Init application\n");
  /* Enable DWT so DWT_CYCCNT works when debugger not attached */
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;

  /* screen init */
  memset(lcd_bg_buffer, 0, sizeof(lcd_bg_buffer));
  CACHE_OP(SCB_CleanInvalidateDCache_by_Addr(lcd_bg_buffer, sizeof(lcd_bg_buffer)));
  memset(lcd_fg_buffer, 0, sizeof(lcd_fg_buffer));
  CACHE_OP(SCB_CleanInvalidateDCache_by_Addr(lcd_fg_buffer, sizeof(lcd_fg_buffer)));
  Display_init();

  /* create buffer queues */
  ret = bqueue_init(&nn_input_queue, 2, (uint8_t *[2]){nn_input_buffers[0], nn_input_buffers[1]});
  assert(ret == 0);


  /*** Camera Init ************************************************************/  
  CAM_Init();

  /* sems + mutex init */
  isp_sem = xSemaphoreCreateCountingStatic(1, 0, &isp_sem_buffer);
  assert(isp_sem);
  disp.update = xSemaphoreCreateCountingStatic(1, 0, &disp.update_buffer);
  assert(disp.update);
  disp.lock = xSemaphoreCreateMutexStatic(&disp.lock_buffer);
  assert(disp.lock);

  /* Start LCD Display camera pipe stream */
  CAM_DisplayPipe_Start(lcd_bg_buffer[0], CMW_MODE_CONTINUOUS);

  /* threads init */
  hdl = xTaskCreateStatic(nn_thread_fct, "nn", configMINIMAL_STACK_SIZE * 2, NULL, nn_priority, nn_thread_stack,
                          &nn_thread);
  assert(hdl != NULL);
  hdl = xTaskCreateStatic(dp_thread_fct, "dp", configMINIMAL_STACK_SIZE * 2, NULL, dp_priority, dp_thread_stack,
                          &dp_thread);
  assert(hdl != NULL);
  hdl = xTaskCreateStatic(isp_thread_fct, "isp", configMINIMAL_STACK_SIZE * 2, NULL, isp_priority, isp_thread_stack,
                          &isp_thread);
  assert(hdl != NULL);
}

int CMW_CAMERA_PIPE_FrameEventCallback(uint32_t pipe)
{
  if (pipe == DCMIPP_PIPE1)
    app_main_pipe_frame_event();
  else if (pipe == DCMIPP_PIPE2)
    app_ancillary_pipe_frame_event();

  return HAL_OK;
}

int CMW_CAMERA_PIPE_VsyncEventCallback(uint32_t pipe)
{
  if (pipe == DCMIPP_PIPE1)
    app_main_pipe_vsync_event();

  return HAL_OK;
}
