from pathlib import Path
from collections import Counter
import hashlib
import json
import wave

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
live = root / "kws/live_datasets/20261008_005213_207370"
manifest = json.loads((live / "manifest.json").read_text())

if manifest.get("complete") is not True:
    raise SystemExit("收集清單未標示完成。")

clips = manifest["clips"]
expected = Counter({
    ("train", "cup"): 8,
    ("train", "bottle"): 8,
    ("train", "phone"): 8,
    ("train", "unknown"): 4,
    ("train", "silence"): 4,
    ("holdout", "cup"): 4,
    ("holdout", "bottle"): 4,
    ("holdout", "phone"): 4,
    ("holdout", "unknown"): 2,
    ("holdout", "silence"): 2,
})
counts = Counter((r["split"], r["label"]) for r in clips)
if counts != expected:
    raise SystemExit(f"分組數量不符：{counts}")

seen_files = set()
hash_groups = {}
errors = []

for row in clips:
    path = live / row["file"]
    if row["file"] in seen_files:
        errors.append(f"清單重複引用檔案：{row['file']}")
    seen_files.add(row["file"])

    try:
        with wave.open(str(path), "rb") as wav:
            fmt = (
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getframerate(),
                wav.getnframes(),
                wav.getcomptype(),
            )
            pcm = wav.readframes(wav.getnframes())

        if fmt != (1, 2, 16000, 16000, "NONE"):
            errors.append(f"音訊格式不符：{row['file']}：{fmt}")
        if len(pcm) != 32000:
            errors.append(f"音訊長度不符：{row['file']}")

        digest = hashlib.sha256(pcm).hexdigest()
        if digest != row["pcm_sha256"]:
            errors.append(f"音訊雜湊不符：{row['file']}")

        hash_groups.setdefault(digest, []).append(row)
    except Exception as exc:
        errors.append(f"讀取失敗：{row['file']}：{exc}")

for rows in hash_groups.values():
    if len({r["split"] for r in rows}) > 1:
        errors.append(
            "訓練與保留測試有完全相同音訊："
            + ", ".join(r["file"] for r in rows)
        )

if errors:
    print("\n".join(errors))
    raise SystemExit("檢查未通過，尚未修改任何資料。")

print("【錄音檢查通過】")
print("48 個檔案：單聲道、16 位元、16000 Hz、每段一秒。")
print("音訊雜湊全部符合，兩組沒有完全相同的音訊。")
print("訓練 32 段；保留測試 16 段。")

print("\n【目前訓練程式】")
script = root / "kws/train_kws.py"
if not script.is_file():
    raise SystemExit(f"找不到：{script}")
print("路徑：", script)
print(script.read_text())

print("\n【目前原始資料集】")
pointer = root / "kws/dataset_current.txt"
dataset = Path(pointer.read_text().strip()).expanduser()
if not dataset.is_absolute():
    raise SystemExit(f"資料集指標不是絕對路徑：{dataset}")

old = json.loads((dataset / "manifest.json").read_text())
print("路徑：", dataset)
print("清單欄位：", list(old))
print("類別順序：", old.get("labels"))
print("各組數量：")
for key, count in sorted(Counter(
    (r["split"], r["label"]) for r in old["clips"]
).items()):
    print(key, count)

print("第一筆資料格式：")
print(json.dumps(old["clips"][:1], ensure_ascii=False, indent=2))

print("\n【語音目錄內的程式與設定檔】")
for path in sorted((root / "kws").iterdir()):
    if path.is_file() and path.suffix in (
        ".py", ".sh", ".json", ".txt", ".yaml", ".yml"
    ):
        print(path.name)
