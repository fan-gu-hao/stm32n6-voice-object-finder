from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import numpy as np

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
ref = root / "kws/comparison/20261007_192902_246036"
meta = json.loads((ref / "reference.json").read_text())

kws = fw / "Src/finder_kws.c"
app = fw / "Src/app.c"
control = fw / "Inc/finder_kws_compare.h"
data_header = fw / "Inc/finder_kws_compare_data.h"
marker = "FINDER_KWS_COMPARE_V1"

original_kws = kws.read_text()
original_app = app.read_text()

if (
    marker in original_kws or marker in original_app
    or control.exists() or data_header.exists()
):
    raise SystemExit("比對程式或標頭已存在，停止以免重複修改。")

if "LL_ATON_Cache_NPU_Clean_Invalidate_Range" not in original_kws:
    raise SystemExit("找不到先前的 NPU 快取修正，尚未修改。")

checks = {
    fw / "Model/kws/kws_int8.tflite": "model_sha256",
    fw / "Inc/finder_kws_tables.h": "tables_sha256",
}
for path, key in checks.items():
    if hashlib.sha256(path.read_bytes()).hexdigest() != meta[key]:
        raise SystemExit(f"產生參考資料後，檔案已變動：{path}")

labels = ["cup", "bottle", "phone", "unknown", "silence"]
if meta["labels"] != labels:
    raise SystemExit("參考資料的類別順序不符。")

with np.load(ref / "reference.npz", allow_pickle=False) as bundle:
    arrays = {
        name: bundle[name].copy()
        for name in ("pcm", "inputs", "outputs")
    }

for name, shape, dtype in (
    ("pcm", (5, 16000), np.int16),
    ("inputs", (5, 637), np.int8),
    ("outputs", (5, 5), np.int8),
):
    if arrays[name].shape != shape or arrays[name].dtype != dtype:
        raise SystemExit(f"對照資料格式不符：{name}")

# 將固定錄音、模型輸入及預期輸出轉成 C 陣列。
header = [
    "#ifndef FINDER_KWS_COMPARE_DATA_H",
    "#define FINDER_KWS_COMPARE_DATA_H",
    "#include <stdint.h>",
    "#define KWS_REF_COUNT 5",
    "#define KWS_REF_FEATURES 637",
    "static const char *const kws_ref_names[5] = {"
    + ", ".join(json.dumps(s) for s in labels) + "};",
]

for name, ctype in (
    ("pcm", "int16_t"),
    ("inputs", "int8_t"),
    ("outputs", "int8_t"),
):
    values = arrays[name]
    header.append(
        f"static const {ctype} kws_ref_{name}[5][{values.shape[1]}] = {{"
    )
    for row in values:
        header.append("  {")
        for i in range(0, len(row), 20):
            header.append(
                "    " + ", ".join(str(int(v)) for v in row[i:i+20]) + ","
            )
        header.append("  },")
    header.append("};")

header.append("#endif\n")

def once(text, before, after):
    if text.count(before) != 1:
        raise SystemExit("修改位置與預期不同，尚未寫入：\n" + before)
    return text.replace(before, after, 1)

hook = r'''
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

'''

updated_kws = once(
    original_kws,
    '#include "finder_kws.h"',
    '#include "finder_kws.h"\n'
    '#include "finder_kws_compare.h"\n'
    '#include <stdio.h>'
)

updated_kws = once(
    updated_kws,
    "int finder_kws_classify(",
    hook + "int finder_kws_classify("
)

updated_kws = once(
    updated_kws,
    "  encode_mfcc(pcm, (int8_t *)input_ptr);",
    '''#if FINDER_KWS_COMPARE_ENABLED
  compare_encode(pcm, (int8_t *)input_ptr);
#else
  encode_mfcc(pcm, (int8_t *)input_ptr);
#endif'''
)

updated_kws += r'''
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
'''

updated_app = once(
    original_app,
    '#include "finder_kws.h"',
    '#include "finder_kws.h"\n#include "finder_kws_compare.h"'
)

updated_app = once(
    updated_app,
    "  ret = finder_mic_start();",
    '''  /* FINDER_KWS_COMPARE_V1 */
#if FINDER_KWS_COMPARE_ENABLED
  finder_kws_compare();
#endif
  ret = finder_mic_start();'''
)

control_text = '''#ifndef FINDER_KWS_COMPARE_H
#define FINDER_KWS_COMPARE_H
#define FINDER_KWS_COMPARE_ENABLED 1
#if FINDER_KWS_COMPARE_ENABLED
void finder_kws_compare(void);
#endif
#endif
'''

backup = root / "backups" / datetime.now().strftime(
    "before_kws_compare_%Y%m%d_%H%M%S_%f"
)
backup.mkdir(parents=True)
shutil.copy2(kws, backup / "finder_kws.c")
shutil.copy2(app, backup / "app.c")

data_header.write_text("\n".join(header))
control.write_text(control_text)
kws.write_text(updated_kws)
app.write_text(updated_app)

print("對照資料：", ref)
print("修改前備份：", backup)
print("已加入兩條比對路徑：INPUT（模型輸入）、PCM（原始錄音）。")
print("開機比對完成後，會繼續執行原本的尋物流程。")
