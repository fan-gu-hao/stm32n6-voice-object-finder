from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import json
import os
import select
import subprocess
import termios
import time
import wave
import zlib

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
port = os.environ["N6_SERIAL_PORT"]

build = Path(
    (root / "output/finder_collection_current.txt").read_text().strip()
)
plan = json.loads((build / "collection_plan.json").read_text())
if len(plan) != 48:
    raise SystemExit("收集計畫不符。")

out = root / "kws/live_datasets" / datetime.now().strftime(
    "%Y%m%d_%H%M%S_%f"
)
out.mkdir(parents=True, exist_ok=False)
report = {
    "complete": False,
    "build": str(build),
    "plan": plan,
    "clips": [],
}

def save_manifest():
    temp = out / "manifest.tmp"
    temp.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(out / "manifest.json")

save_manifest()

subprocess.run([
    "stty", "-F", port, "115200", "raw", "-echo",
    "cs8", "-cstopb", "-parenb", "-crtscts",
    "-ixon", "-ixoff", "clocal",
], check=True)

fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
pending, packet, cue = b"", None, None
started = done = False

try:
    termios.tcflush(fd, termios.TCIFLUSH)
    print("已就緒。現在按一次 RESET，接著只依提示說話。", flush=True)
    print("需要約 8–10 分鐘。資料：", out, flush=True)
    deadline = time.monotonic() + 90

    with (out / "serial.log").open("w", encoding="utf-8") as log:
        while not done:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "接收逾時；已收到的錄音保留在上述目錄。"
                )

            if not select.select([fd], [], [], 0.2)[0]:
                continue

            data = os.read(fd, 8192)
            if not data:
                raise RuntimeError("串列連線中斷。")
            pending += data

            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode("ascii", errors="replace").strip()
                log.write(line + "\n")

                if not line.startswith("LIVE,"):
                    continue
                parts = line.split(",")

                if not started:
                    if parts[:3] != ["LIVE", "CUE", "0"]:
                        continue
                    started = True

                deadline = time.monotonic() + 30
                kind = parts[1]

                if kind == "CUE":
                    index = int(parts[2])
                    if index != len(report["clips"]) or index >= len(plan):
                        raise RuntimeError(
                            "收集順序不符；可能中途重設或有其他程式讀取串列埠。"
                        )

                    cue = plan[index]
                    if parts[3] != cue["label"]:
                        raise RuntimeError("板上收集版本與計畫不同。")

                    message = (
                        "保持安靜約四秒。"
                        if cue["label"] == "silence"
                        else "現在說一次 " + cue["say"] + "，說完保持安靜。"
                    )
                    print(
                        f"\n[{index+1}/48｜{cue['split']}] {message}",
                        flush=True,
                    )

                elif kind == "B":
                    if (
                        cue is None
                        or int(parts[2]) != cue["index"]
                        or parts[3] != cue["label"]
                    ):
                        raise RuntimeError("音訊標頭順序不符。")

                    packet = {
                        "data": bytearray(),
                        "time_ms": int(parts[4]),
                        "peak": int(parts[5]),
                    }
                    print(
                        "傳回錄音中，約六秒；請等待下一個提示。",
                        flush=True,
                    )

                elif kind == "D":
                    if (
                        packet is None
                        or int(parts[2]) != len(packet["data"])
                    ):
                        raise RuntimeError("音訊資料有缺漏。")
                    packet["data"].extend(bytes.fromhex(parts[3]))

                elif kind == "E":
                    if (
                        packet is None
                        or len(packet["data"]) != 32642
                        or zlib.crc32(packet["data"]) != int(parts[2], 16)
                    ):
                        raise RuntimeError("音訊傳輸校驗失敗。")

                    pcm = bytes(packet["data"][:32000])
                    name = (
                        f"{cue['split']}/{cue['label']}/"
                        f"take_{cue['index']+1:02d}.wav"
                    )
                    path = out / name
                    path.parent.mkdir(parents=True, exist_ok=True)

                    with wave.open(str(path), "wb") as wav:
                        wav.setparams(
                            (1, 2, 16000, 16000, "NONE", "not compressed")
                        )
                        wav.writeframes(pcm)

                    report["clips"].append(dict(
                        cue,
                        file=name,
                        peak=packet["peak"],
                        time_ms=packet["time_ms"],
                        pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                    ))
                    save_manifest()
                    print("已儲存：", name, flush=True)

                    if cue["label"] != "silence" and packet["peak"] < 2500:
                        print(
                            "提醒：這段音量偏低，請記下檔名，"
                            "稍後確認有沒有錄到發音。",
                            flush=True,
                        )

                    packet, cue = None, None

                elif kind == "ERROR":
                    raise RuntimeError(line)

                elif kind == "DONE":
                    if len(report["clips"]) != 48:
                        raise RuntimeError("48 段錄音尚未收齊。")
                    done = True
                    break
finally:
    os.close(fd)

report["complete"] = True
save_manifest()
(root / "kws/live_dataset_current.txt").write_text(str(out) + "\n")

counts = Counter(
    (r["split"], r["label"]) for r in report["clips"]
)
print("\n收集完成：")
for label in ("cup", "bottle", "phone", "unknown", "silence"):
    print(
        f"{label:7}：訓練 {counts['train', label]}；"
        f"保留測試 {counts['holdout', label]}"
    )

print("資料：", out)
print("這些資料尚未訓練；板子目前仍是收集模式。")
