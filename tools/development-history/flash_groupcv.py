from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import subprocess

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
out = Path(
    (root / "output/finder_groupcv_build_current.txt").read_text().strip()
)
manifest = json.loads((out / "flash_manifest.json").read_text())
cli = Path(manifest["programmer"])
loader = Path(manifest["loader"])

expected = [
    ("kws_weights.bin", "0x70700000"),
    ("finder_signed.bin", "0x70100000"),
]
if [(x["file"], x["address"]) for x in manifest["images"]] != expected:
    raise SystemExit("燒錄清單或位址不符。")
if not cli.is_file() or not os.access(cli, os.X_OK) or not loader.is_file():
    raise SystemExit("找不到燒錄工具或外部快閃記憶體載入程式。")

for item, limit in zip(manifest["images"], (64 * 1024, 1024 * 1024)):
    data = (out / item["file"]).read_bytes()
    if not 0 < len(data) <= limit:
        raise SystemExit("映像大小不符：" + item["file"])
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit("檔案已變更：" + item["file"])

raw = (out / "finder.bin").read_bytes()
signed = (out / "finder_signed.bin").read_bytes()
if len(raw) < 8 or signed[0x400:0x400 + len(raw)] != raw:
    raise SystemExit("簽章映像內容不符。")

print("燒錄來源：", out, flush=True)
for item in manifest["images"]:
    command = [
        str(cli), "-c", "port=SWD", "mode=HOTPLUG", "ap=1",
        "freq=1000", "sn=" + os.environ["N6_PROBE_SERIAL"],
        "-el", str(loader), "-hardRst",
        "-w", str(out / item["file"]), item["address"], "-v",
    ]
    print(
        "\n寫入並驗證：", item["file"], "→", item["address"],
        flush=True,
    )
    with (out / ("flash_" + item["file"] + ".log")).open("w") as log:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
            errors="replace", bufsize=1,
        )
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
        code = process.wait()
    if code:
        raise SystemExit(
            "燒錄尚未全部完成；請保留目前開機開關設定並貼回錯誤。"
        )

(out / "flash_verified.json").write_text(json.dumps({
    "verified_at": datetime.now().astimezone().isoformat(),
    "images": manifest["images"],
}, indent=2) + "\n")
(root / "output/finder_voice_current.txt").write_text(str(out) + "\n")
(root / "kws/model_current.txt").write_text(manifest["candidate"] + "\n")

print("\n兩個映像均已寫入並通過驗證。")
print("請斷電，將 BOOT0=L、BOOT1=L，再上電進行即時測試。")
