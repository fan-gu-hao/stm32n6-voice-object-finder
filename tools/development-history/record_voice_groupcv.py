from pathlib import Path
from datetime import datetime
import json
import os
import select
import subprocess
import termios
import time

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
port = os.environ["N6_SERIAL_PORT"]

subprocess.run([
    "stty", "-F", port, "115200", "raw", "-echo", "cs8",
    "-cstopb", "-parenb", "-crtscts", "-ixon", "-ixoff", "clocal",
], check=True)

path = root / "logs" / (
    "voice_groupcv_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".log"
)
path.parent.mkdir(parents=True, exist_ok=True)
stages = [
    ("silence", None), ("cup", "cup"), ("bottle", "bottle"),
    ("phone", "phone"), ("bottle", "bottle"), ("cup", "cup"),
    ("phone", "phone"), ("unknown", "hello"), ("silence", None),
]
summary = []
fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)

try:
    termios.tcflush(fd, termios.TCIFLUSH)
    pending = b""
    with path.open("w") as log:
        for index, (label, word) in enumerate(stages, 1):
            cue = (
                "保持安靜六秒。" if word is None
                else "現在說一次 " + word + "，說完保持安靜。"
            )
            print(f"\n[{index}/{len(stages)}] {cue}", flush=True)
            log.write(
                f"\nSTAGE,{index},expected={label},word={word or '-'}\n"
            )
            rows = []
            end = time.monotonic() + 6

            while time.monotonic() < end:
                ready, _, _ = select.select(
                    [fd], [], [],
                    max(0, min(0.05, end - time.monotonic())),
                )
                if not ready:
                    continue
                block = os.read(fd, 65536)
                if not block:
                    raise SystemExit("串列連線中斷。")
                pending += block

                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    text = line.decode(errors="replace").strip()
                    log.write(text + "\n")
                    if text.startswith(("KWS,", "VOICE,")):
                        row = dict(
                            part.split("=", 1)
                            for part in text.split(",") if "=" in part
                        )
                        row["type"] = text.split(",", 1)[0]
                        rows.append(row)

            summary.append((label, rows))
            log.flush()
        if pending:
            log.write("PARTIAL," + pending.decode(errors="replace") + "\n")
finally:
    os.close(fd)

def maximum(rows, key):
    values = [
        int(r[key]) for r in rows
        if r.get(key, "").lstrip("-").isdigit()
    ]
    return max(values) if values else "-"

print("\n【各階段紀錄；accept=1 次數是紀錄行數】")
for index, (label, rows) in enumerate(summary, 1):
    kws = [r for r in rows if r["type"] == "KWS"]
    accepted = [
        r.get("class", "?") for r in kws if r.get("accept") == "1"
    ]
    same = [
        r for r in kws if r.get("class", "").lower() == label
    ]
    print(
        f"{index}. {label:7} KWS={len(kws):2} accept=1:{accepted} "
        f"目標最高分={maximum(kws, label)} "
        f"同類最高hits={maximum(same, 'hits')} "
        f"peak={maximum(rows, 'peak')} clip={maximum(rows, 'clip')}"
    )

path.with_suffix(".json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
)
print("日誌：", path)
