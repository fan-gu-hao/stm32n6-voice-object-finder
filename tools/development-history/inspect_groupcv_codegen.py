from pathlib import Path
import hashlib
import json
import re

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
deployed = fw / "Model/kws"

out = (
    root / "output"
    / "finder_groupcv_codegen_20261008_022527_741465"
)
stage = out / "codegen"
generated = stage / "st_ai_output"

# 只檢查正式輸出，不搜尋 st_ai_ws 中間工作目錄。
names = (
    "kws_network.c",
    "kws_network.h",
    "stai_kws_network.c",
    "stai_kws_network.h",
    "kws_network_atonbuf.xSPI2.raw",
    "kws_network_c_info.json",
)

for name in names:
    path = generated / name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit("正式產物缺少或為空：" + str(path))

expected_hash = (out / "model_sha256.txt").read_text().strip()
actual_hash = hashlib.sha256(
    (stage / "kws_int8.tflite").read_bytes()
).hexdigest()

if actual_hash != expected_hash:
    raise SystemExit("產碼來源模型的雜湊不符，請貼回此訊息。")

print("【正式產碼檔案】")
for name in names:
    path = generated / name
    print(name, path.stat().st_size, "位元組")

config = json.loads((stage / "config.json").read_text())

print("\n【新模型量化參數】")
for key in ("input_quantization", "output_quantization"):
    print(key, config[key])

print("\n【目前前處理表頭的巨集與陣列名稱】")
header = (fw / "Inc/finder_kws_tables.h").read_text()

for line in header.splitlines():
    if re.match(r"^\s*#\s*define\b", line):
        print(line)

for declaration in re.findall(
    r"(?:static\s+)?const\s+float\s+\w+\s*"
    r"(?:\[[^\]]*\]\s*)*",
    header,
):
    print(declaration.strip() + ";")

print("\n【目前收集／比對模式】")
control = (fw / "Inc/finder_kws_compare.h").read_text()
for line in control.splitlines():
    if re.match(r"^\s*#\s*define\s+FINDER_KWS_", line):
        print(line)

print("\n【本次產碼使用的編譯設定】")
print((stage / "kws_neuralart.json").read_text())

print("\n【本次產碼使用的記憶體池】")
print((stage / "kws.mpool").read_text())

(root / "output/kws_codegen_current.txt").write_text(
    str(out) + "\n"
)

print("\n檢查完成，已記錄產碼目錄：", out)
print("正式產物目錄：", generated)
