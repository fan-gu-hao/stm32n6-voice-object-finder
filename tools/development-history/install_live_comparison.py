from pathlib import Path
from datetime import datetime
import re
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
paths = [
    fw / "Src/finder_kws.c",
    fw / "Src/app.c",
    fw / "Inc/finder_kws_compare.h",
]
kws, app, control = [p.read_text(encoding="utf-8") for p in paths]
marker = "FINDER_KWS_LIVE_CAPTURE_V1"

if any(marker in text for text in (kws, app, control)):
    raise SystemExit("即時擷取修改已存在，請接著編譯，勿重複貼入。")

def once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit("修改位置與預期不同，尚未寫入：\n" + old)
    return text.replace(old, new, 1)

if "LL_ATON_Cache_NPU_Clean_Invalidate_Range" not in kws:
    raise SystemExit("缺少先前的快取修正，尚未修改。")

control = once(
    control,
    "#define FINDER_KWS_COMPARE_ENABLED 1",
    "#define FINDER_KWS_COMPARE_ENABLED 0",
)

control = once(
    control,
    "#define FINDER_KWS_COMPARE_H",
    '''#define FINDER_KWS_COMPARE_H
#include "finder_kws.h"
/* FINDER_KWS_LIVE_CAPTURE_V1 */
#define FINDER_KWS_LIVE_CAPTURE 1
#if FINDER_KWS_LIVE_CAPTURE
void finder_kws_live_capture(const int16_t *pcm,
                             const finder_kws_result_t *result);
#endif''',
)

kws = once(
    kws,
    "int finder_kws_classify(",
    '''/* FINDER_KWS_LIVE_CAPTURE_V1 */
#if FINDER_KWS_LIVE_CAPTURE
static unsigned live_stage;
static int8_t live_input[STAI_KWS_NETWORK_IN_1_SIZE_BYTES];
#endif

int finder_kws_classify(''',
)

kws = once(
    kws,
    "  prepare_input_cache(input_ptr, STAI_KWS_NETWORK_IN_1_SIZE_BYTES);",
    '''#if FINDER_KWS_LIVE_CAPTURE
  if (live_stage < 4U)
    memcpy(live_input, input_ptr, sizeof(live_input));
#endif
  prepare_input_cache(input_ptr, STAI_KWS_NETWORK_IN_1_SIZE_BYTES);''',
)

match = re.search(
    r"(?ms)^static void finder_voice_poll\(void\)\s*\{.*?^\}", app
)
if not match:
    raise SystemExit("找不到語音判定函式，尚未修改。")

body = once(
    match[0],
    "  unsigned best = 0;",
    '''  /* FINDER_KWS_LIVE_CAPTURE_V1 */
#if FINDER_KWS_LIVE_CAPTURE
  finder_kws_live_capture(voice_pcm, &result);
#endif
  unsigned best = 0;''',
)
app = app[:match.start()] + body + app[match.end():]

kws += r'''
#if FINDER_KWS_LIVE_CAPTURE
_Static_assert(FINDER_KWS_SAMPLES == 16000, "Live PCM size mismatch");
_Static_assert(STAI_KWS_NETWORK_IN_1_SIZE_BYTES == 637, "Live input mismatch");
_Static_assert(FINDER_KWS_CLASSES == 5, "Live output mismatch");

static int16_t live_pcm[16000];
static int8_t live_features[637], live_output[5];
static const char *const live_labels[] = {
  "silence", "cup", "bottle", "phone"
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
  static float best_command;

  if (live_stage >= 4U) return;

  uint32_t now = HAL_GetTick();
  if (!started) {
    start = now;
    selected = 0;
    best_energy = 0;
    best_command = -1.0f;
    started = 1;
    printf("LIVE,CUE,%u,%s\n", live_stage, live_labels[live_stage]);
    return;
  }

  uint32_t elapsed = now - start;
  if (elapsed < 1000U) return;

  if (elapsed >= 4500U) {
    if (!selected) {
      printf("LIVE,ERROR,no_sample\n");
      live_stage = 4U;
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
    if (live_stage == 4U) printf("LIVE,DONE\n");
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
  float command = fmaxf(result->scores[0],
                        fmaxf(result->scores[1], result->scores[2]));

  /* 靜音：保留最像命令的片段；說話：保留音訊能量最大的片段。 */
  if (!selected || (live_stage == 0U ? command > best_command
                                     : energy > best_energy)) {
    selected = 1;
    best_energy = energy;
    best_command = command;
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
'''

backup = root / "backups" / datetime.now().strftime(
    "before_live_capture_%Y%m%d_%H%M%S_%f"
)
for path, text in zip(paths, (kws, app, control)):
    dest = backup / path.relative_to(fw)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    path.write_text(text, encoding="utf-8")
    print("已修改：", path.relative_to(fw))

print("備份：", backup)
print("已關閉固定音檔比對，改為四段即時音訊擷取。")
