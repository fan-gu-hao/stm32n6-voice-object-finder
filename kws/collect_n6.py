from pathlib import Path
from datetime import datetime
import json
import os
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
MIC_ROOT = Path(os.environ.get("N6_MIC_ROOT", str(Path.home() / "STM32N6ai/course15_n6_mic_test"))).expanduser().resolve()
TOOLS = Path(__file__).resolve().parent / "recording_tools"
START = TOOLS / "n6_mic_start_and_record.sh"
RECEIVER = TOOLS / "n6_receive_wav.py"
RECORDINGS = MIC_ROOT / "recordings"
DATA = ROOT / "kws/data_raw"

PLAN = [("cup", 12), ("bottle", 12), ("phone", 12),
        ("unknown", 8), ("silence", 3)]

OTHER_WORDS = [
    "yes、no、stop、go",
    "book、chair、table、light",
    "water、coffee、screen、desk",
    "pen、keys、wallet、bag",
    "one、two、three、four",
    "hello、morning、today、thanks",
    "left、right、up、down",
    "computer、window、door、camera",
]

def check_wav(path):
    with wave.open(str(path), "rb") as wav:
        actual = (
            wav.getframerate(), wav.getnchannels(),
            wav.getsampwidth(), wav.getnframes()
        )
    if actual != (16000, 1, 2, 80000):
        raise RuntimeError(f"錄音格式不符：{path}\n實際格式：{actual}")

def main():
    for name in ("N6_STLINK_SERIAL", "N6_MIC_PORT"):
        if not os.environ.get(name):
            raise RuntimeError(f"請先設定環境變數 {name}，詳見 recording_tools/README.md。")
    for path in (START, RECEIVER):
        if not path.is_file():
            raise FileNotFoundError(f"找不到已驗證的錄音程式：{path}")

    DATA.mkdir(parents=True, exist_ok=True)
    first_recording = True
    session = datetime.now().isoformat(timespec="seconds")

    for label, count in PLAN:
        folder = DATA / label
        folder.mkdir(exist_ok=True)

        for number in range(1, count + 1):
            destination = folder / f"take_{number:02d}.wav"
            if destination.exists():
                check_wav(destination)
                continue

            if label == "silence":
                instruction = "保持安靜，讓板子錄下正常環境底噪。"
            elif label == "unknown":
                instruction = "依序說：" + OTHER_WORDS[number - 1]
            else:
                instruction = f"說 4 次 {label}，每次之間稍微停頓。"

            print(f"\n===== {label}：第 {number}/{count} 段 =====", flush=True)
            print(instruction, flush=True)
            print("看到「錄音中」或綠燈亮起後才開始。", flush=True)
            input("準備好後按 Enter；Ctrl+C 可中止並保留已完成資料。")

            before = set(RECORDINGS.glob("n6_mic_*.wav"))

            if first_recording:
                command = ["bash", str(START)]
            else:
                command = [sys.executable, "-u", str(RECEIVER)]

            subprocess.run(command, check=True)
            first_recording = False

            created = set(RECORDINGS.glob("n6_mic_*.wav")) - before
            if len(created) != 1:
                raise RuntimeError(
                    f"預期新增一個錄音檔，實際找到 {len(created)} 個："
                    + ", ".join(map(str, created))
                )

            source = created.pop()
            check_wav(source)
            shutil.copy2(source, destination)

            metadata = {
                "label": label,
                "session": session,
                "source": str(source),
                "sample_rate": 16000,
                "duration_seconds": 5,
            }
            destination.with_suffix(".json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"已收錄：{destination}", flush=True)

    print("\n本輪錄音資料收集完成：")
    for label, count in PLAN:
        files = list((DATA / label).glob("take_*.wav"))
        print(f"  {label:8s}：{len(files)}/{count} 段")
    print(f"資料位置：{DATA}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中止；下次執行會接續尚未完成的錄音。")
        raise SystemExit(130)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"\n停止：{error}")
