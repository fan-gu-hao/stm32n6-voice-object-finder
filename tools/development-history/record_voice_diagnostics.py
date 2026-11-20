from pathlib import Path
from datetime import datetime
import os
import select
import subprocess
import termios
import time

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
port = os.environ["N6_SERIAL_PORT"]
stages = [
    "silence", "cup", "bottle", "phone",
    "bottle", "cup", "phone", "silence"
]

logdir = root / "logs"
logdir.mkdir(exist_ok=True)
logpath = logdir / datetime.now().strftime(
    "voice_labelled_%Y%m%d_%H%M%S.log"
)

subprocess.run([
    "stty", "-F", port, "115200", "raw", "-echo",
    "cs8", "-cstopb", "-parenb", "-crtscts",
    "-ixon", "-ixoff", "clocal"
], check=True)

fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
records = [[] for _ in stages]
pending = b""
current = -1

print("以平常音量說話，保持與訓練錄音相近的距離。每次只說一次。")
print("請勿按 USER1 或 RESET。完整紀錄：", logpath, flush=True)

try:
    termios.tcflush(fd, termios.TCIFLUSH)
    start = time.monotonic()

    with logpath.open("w") as log:
        while True:
            elapsed = time.monotonic() - start
            index = int(elapsed // 6)
            if index >= len(stages):
                break

            if index != current:
                current = index
                label = stages[index]
                message = (
                    "保持安靜。" if label == "silence"
                    else f"現在說一次 {label}，說完保持安靜。"
                )
                print(f"\n[{elapsed:4.1f} 秒] {message}", flush=True)
                log.write(
                    f"PROMPT,time={elapsed:.3f},label={label}\n"
                )

            if not select.select([fd], [], [], 0.05)[0]:
                continue

            chunk = os.read(fd, 8192)
            if not chunk:
                raise SystemExit("串列連線已中斷。")
            pending += chunk

            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode(
                    "ascii", errors="replace"
                ).strip()
                log.write(f"{elapsed:.3f} {line}\n")

                if line.startswith(("KWS,", "VOICE,")):
                    row = dict(
                        x.split("=", 1)
                        for x in line.split(",")[1:]
                        if "=" in x
                    )
                    row["type"] = line.split(",")[0]
                    records[current].append(row)

                    if row.get("accept") == "1":
                        print(
                            "  接受命令：",
                            row.get("class"),
                            flush=True
                        )
finally:
    os.close(fd)

if not any("hits" in r for rows in records for r in rows):
    raise SystemExit(
        "沒有收到詳細候選紀錄，請貼上日誌並確認前兩段已完成。"
    )

print("\n每個時段的結果：")
for label, rows in zip(stages, records):
    kws = [
        r for r in rows
        if r.get("type") == "KWS" and "hits" in r
    ]
    accepted = [
        r["class"] for r in kws
        if r.get("accept") == "1"
    ]
    peak = max(
        [int(r.get("peak", 0)) for r in rows], default=0
    )
    clipped = max(
        [int(r.get("clip", 0)) for r in kws], default=0
    )
    score = max(
        [int(r.get(label, 0)) for r in kws], default=0
    )
    hits = max([
        int(r["hits"]) for r in kws
        if r.get("class", "").lower() == label
    ], default=0)

    print(
        f"提示={label:7}；接受={','.join(accepted) or '無'}；"
        f"模型視窗數={len(kws)}；"
        f"該詞最高分={str(score)+'%' if kws else '未推論'}；"
        f"連續達標最多={hits}；峰值={peak}；"
        f"推論視窗滿刻度樣本最多={clipped}"
    )

print("完整紀錄：", logpath)
