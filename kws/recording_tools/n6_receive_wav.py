from pathlib import Path
from datetime import datetime
import array
import fcntl
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import time
import wave
import zlib

PORT = os.environ.get("N6_MIC_PORT", "")
ROOT = Path(os.environ.get("N6_MIC_ROOT", str(Path.home() / "STM32N6ai/course15_n6_mic_test"))).expanduser().resolve()
READY = b"N6MIC_READY,1,16000,1,16,80000"

def capture(port):
    fd = os.open(str(port), os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    previous = None
    buffer = bytearray()

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.ioctl(fd, termios.TIOCEXCL)

        previous = termios.tcgetattr(fd)
        settings = termios.tcgetattr(fd)
        settings[0] = settings[1] = settings[3] = 0
        settings[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        settings[4] = settings[5] = termios.B115200
        settings[6][termios.VMIN] = settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        termios.tcflush(fd, termios.TCIFLUSH)

        def fill(deadline):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise TimeoutError("等待資料逾時，請確認板子已執行新版錄音程式。")
            try:
                data = os.read(fd, 8192)
            except BlockingIOError:
                return
            if not data:
                raise RuntimeError("串列連線中斷。")
            buffer.extend(data)

        def line(timeout):
            deadline = time.monotonic() + timeout
            while b"\n" not in buffer:
                if len(buffer) > 512:
                    raise RuntimeError(f"控制訊息過長，前 80 位元組：{bytes(buffer[:80])!r}")
                fill(deadline)

            pos = buffer.index(b"\n")
            if pos > 512:
                raise RuntimeError(f"控制訊息過長，前 80 位元組：{bytes(buffer[:80])!r}")

            result = bytes(buffer[:pos]).rstrip(b"\r")
            del buffer[:pos + 1]
            if result.startswith(b"N6MIC_ERROR,"):
                raise RuntimeError(result.decode("ascii", errors="replace"))
            return result

        def exact(size, timeout):
            deadline = time.monotonic() + timeout
            while len(buffer) < size:
                fill(deadline)
            result = bytes(buffer[:size])
            del buffer[:size]
            return result

        print("確認板上的錄音程式…", flush=True)
        # N6_HANDSHAKE_DIAG_V2
        identified = False
        print(f"預期回覆：{READY!r}", flush=True)
        for attempt in range(1, 4):
            print(f"交握嘗試：{attempt}/3", flush=True)
            sent = os.write(fd, b"?")
            if sent != 1:
                raise RuntimeError(f"查詢指令未完整送出：{sent} 位元組。")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                try:
                    reply = line(max(0, deadline - time.monotonic()))
                except TimeoutError:
                    print("這次等待逾時。", flush=True)
                    break
                print(f"實際收到：{reply!r}", flush=True)
                if reply == READY:
                    identified = True
                    break
                print(f"十六進位：{reply.hex(' ')}", flush=True)
            if identified:
                break
        if not identified:
            raise RuntimeError("三次查詢仍未收到正確回覆，請貼上交握紀錄。")

        print("請準備說話；即將錄音約 5 秒。", flush=True)
        if os.write(fd, b"R") != 1:
            raise RuntimeError("無法送出錄音指令。")

        deadline = time.monotonic() + 3
        while True:
            response = line(max(0, deadline - time.monotonic()))
            if response == b"N6MIC_RECORDING,80000":
                break
            if response not in (READY, b"") or time.monotonic() >= deadline:
                raise RuntimeError("未收到錄音開始回應。")

        print("錄音中，綠燈應亮起，請說話。", flush=True)
        header = line(16)
        match = re.fullmatch(
            rb"N6MIC_DATA,16000,1,16,160000,([0-9A-Fa-f]{8})", header
        )
        if match is None:
            raise RuntimeError(f"音訊標頭不符：{header!r}")

        print("錄音完成，正在接收音訊，約需 14 秒…", flush=True)
        pcm = exact(160000, 30)
        trailer = b"\nN6MIC_DONE\n"
        if exact(len(trailer), 3) != trailer:
            raise RuntimeError("音訊結尾不完整。")
        if zlib.crc32(pcm) != int(match.group(1), 16):
            raise RuntimeError("CRC32 校驗失敗，未儲存音訊。")
        return pcm

    finally:
        try:
            if previous is not None:
                termios.tcsetattr(fd, termios.TCSANOW, previous)
        finally:
            try:
                fcntl.ioctl(fd, termios.TIOCNXCL)
            finally:
                os.close(fd)

def save(pcm, root):
    folder = Path(root) / "recordings"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / (
        "n6_mic_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".wav"
    )

    with output.open("xb") as file:
        with wave.open(file, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(pcm)

    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()

    clipped = sum(value in (-32768, 32767) for value in samples)
    print(f"校驗通過，已儲存：{output}")
    print(f"樣本數：{len(samples)}；格式：16000 Hz、單聲道、16 位元、5 秒。")
    print(f"最小值：{min(samples)}；最大值：{max(samples)}；碰到上下限的樣本：{clipped}。")
    return output

def main():
    if not PORT:
        raise RuntimeError("請先設定 N6_MIC_PORT 為實際的串列埠路徑。")
    if shutil.which("fuser"):
        busy = subprocess.run(
            ["fuser", PORT],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if busy.returncode == 0 and busy.stdout.strip():
            raise RuntimeError("串列埠仍被使用，請先停止 cat、minicom 或其他串列監看程式。")

    output = save(capture(PORT), ROOT)

    for name in ("pw-play", "paplay", "aplay"):
        player = shutil.which(name)
        if player:
            print(f"使用 {name}，由電腦目前的音訊輸出播放。", flush=True)
            if subprocess.run([player, str(output)]).returncode == 0:
                return

    print(f"音訊已保存，但未能自動播放：{output}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止接收；重試前請等板子完成這次錄音與傳輸，約 20 秒。")
        raise SystemExit(130)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"錯誤：{error}")
