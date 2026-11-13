#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob
: "${N6_STLINK_SERIAL:?請先設定偵錯器序號 N6_STLINK_SERIAL}"
: "${N6_MIC_PORT:?請先設定串列埠路徑 N6_MIC_PORT}"

N6_IDE="${N6_MIC_IDE:-/opt/st/stm32cubeide_2.2.0}"
N6_ROOT="${N6_MIC_ROOT:-$HOME/STM32N6ai/course15_n6_mic_test}"
N6_EXAMPLE="$N6_ROOT/STM32CubeN6/Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder"
N6_BUILD="$N6_EXAMPLE/STM32CubeIDE/FSBL/Debug"
N6_RECEIVER="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/n6_receive_wav.py"

N6_SERVERS=( "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.stlink-gdb-server.linux64_*/tools/bin/ST-LINK_gdbserver )
N6_GDBS=( "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin/arm-none-eabi-gdb )
N6_CLIS=( "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.linux64_*/tools/bin/STM32_Programmer_CLI )

if (( ${#N6_SERVERS[@]} == 0 || ${#N6_GDBS[@]} == 0 || ${#N6_CLIS[@]} == 0 )); then
    printf '找不到所需的 CubeIDE 偵錯工具。\n'
    exit 1
fi

for N6_TOOL in "${N6_SERVERS[0]}" "${N6_GDBS[0]}" "${N6_CLIS[0]}"; do
    test -x "$N6_TOOL" || {
        printf '工具無法執行：%s\n' "$N6_TOOL"
        exit 1
    }
done

command -v timeout >/dev/null

python3 - "$N6_BUILD" "$N6_RECEIVER" <<'PY'
from pathlib import Path
import socket
import struct
import sys

build, receiver = map(Path, sys.argv[1:])

for path in (build / "MDF_AudioRecorder_FSBL.elf", receiver):
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"缺少檔案：{path}")

data = (build / "MDF_AudioRecorder_FSBL.bin").read_bytes()

if not 8 <= len(data) <= 255 * 1024:
    raise SystemExit("BIN 大小不符合程式 RAM 區域。")

msp, entry = struct.unpack_from("<II", data)

if msp != 0x34200000 or not (
    entry & 1
    and 0x34180400 <= (entry & ~1) < 0x34180400 + len(data)
):
    raise SystemExit("向量表與這個專案不符，停止載入。")

if b"N6MIC_READY,1,16000,1,16,80000" not in data:
    raise SystemExit("BIN 不是預期的五秒錄音版本。")

with socket.socket() as probe:
    try:
        probe.bind(("127.0.0.1", 61240))
    except OSError:
        raise SystemExit("偵錯連接埠 61240 無法使用，請先結束舊的偵錯工作階段。")

print(f"檢查通過：程式 {len(data)} 位元組")
print(f"初始堆疊：0x{msp:08X}；程式入口：0x{entry:08X}")
PY

N6_LOGDIR="$N6_ROOT/logs/mic_run_$(date +%Y%m%d_%H%M%S)_$$"
mkdir -p "$N6_LOGDIR"
printf '本次日誌：%s\n' "$N6_LOGDIR"

sha256sum \
    "$N6_BUILD/MDF_AudioRecorder_FSBL.elf" \
    "$N6_BUILD/MDF_AudioRecorder_FSBL.bin" \
    "$N6_RECEIVER" > "$N6_LOGDIR/files.sha256"

cat > "$N6_LOGDIR/start.gdb" <<'GDB'
set pagination off
set confirm off
set language c
set remotetimeout 5
set tcp auto-retry on
set tcp connect-timeout 10
set breakpoint pending off

define n6_failed
  printf "\n[N6] STOP: unexpected stop location\n"
  info registers pc lr sp xpsr
  bt 8
  x/2wx 0xE000ED04
  x/6wx 0xE000ED24
  delete breakpoints
  set *(unsigned int *)0xE000EDFC = $n6_old_demcr
  disconnect
  quit 2
end

target remote 127.0.0.1:61240

info registers pc sp msp xpsr control primask basepri faultmask

# 載入前應處於開發啟動模式的 Boot ROM。
if ((unsigned int)$pc < 0x18000000) || ((unsigned int)$pc >= 0x18020000)
  printf "\n[N6] STOP: cold start in BOOT1=H mode is required.\n"
  disconnect
  quit 1
end

# 暫時啟用嚴重錯誤捕捉，保留原本設定以便還原。
set $n6_old_demcr = *(unsigned int *)0xE000EDFC
set *(unsigned int *)0xE000EDFC = $n6_old_demcr | 0x400

# 載入程式並讀取向量表。
restore MDF_AudioRecorder_FSBL.bin binary 0x34180400
set $n6_stack = *(unsigned int *)0x34180400
set $n6_entry = *(unsigned int *)0x34180404

if ($n6_stack != 0x34200000) || ($n6_entry < 0x34180401) || ($n6_entry >= 0x341C0000) || (($n6_entry & 1) == 0)
  n6_failed
end

# 設定核心啟動狀態。
set $control = 0
set $msp = $n6_stack
set $sp = $n6_stack
set $primask = 0
set $basepri = 0
set $faultmask = 0
set $xpsr = 0x01000000
set $pc = $n6_entry & 0xFFFFFFFE

info registers pc sp msp xpsr control primask basepri faultmask

if ((unsigned int)$sp != $n6_stack) || (((unsigned int)$pc & 0xFFFFFFFE) != ($n6_entry & 0xFFFFFFFE))
  n6_failed
end

# 第一個檢查點：確認進入主程式。
hbreak *HardFault_Handler
hbreak *Error_Handler
thbreak *main
continue

if (((unsigned int)$pc & 0xFFFFFFFE) != ((unsigned int)&main & 0xFFFFFFFE))
  n6_failed
end

printf "\n[N6] PASS: reached main\n"

# 第二個檢查點：確認準備傳送識別訊息。
thbreak *MicLine
continue

if (((unsigned int)$pc & 0xFFFFFFFE) != ((unsigned int)&MicLine & 0xFFFFFFFE))
  n6_failed
end

printf "\n[N6] PASS: reached MicLine\n"
x/s $r0

# 檢查完成：清除中斷點、還原捕捉設定、解除偵錯連線。
delete breakpoints
set *(unsigned int *)0xE000EDFC = $n6_old_demcr
detach

printf "\n[N6] Debugger detached; UART recording test follows.\n"
quit
GDB

N6_SERVER_PID=""

n6_cleanup() {
    if [ -n "$N6_SERVER_PID" ]; then
        if jobs -pr | grep -Fxq "$N6_SERVER_PID"; then
            kill "$N6_SERVER_PID" 2>/dev/null || true
        fi
        wait "$N6_SERVER_PID" 2>/dev/null || true
    fi
}

trap n6_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# 啟動偵錯伺服器；最後的 & 代表放到背景執行。
"${N6_SERVERS[0]}" \
    -d -g -m 1 --frequency 950 \
    -i "${N6_STLINK_SERIAL}" \
    -p 61240 \
    -cp "$(dirname "${N6_CLIS[0]}")" \
    -l 4 \
    -f "$N6_LOGDIR/server.log" \
    > "$N6_LOGDIR/server_console.log" 2>&1 &

# 記住剛啟動的伺服器程序編號。
N6_SERVER_PID=$!

printf '正在載入並檢查啟動，最長等待約 45 秒。\n'
cd "$N6_BUILD"

# 批次執行偵錯指令，限制等待時間。
if timeout --signal=INT --kill-after=5s 40s \
    "${N6_GDBS[0]}" \
    -q -nx -batch MDF_AudioRecorder_FSBL.elf \
    -x "$N6_LOGDIR/start.gdb" \
    2>&1 | tee "$N6_LOGDIR/start.log"; then

    printf '已完成載入與脫離偵錯，接著驗證串列錄音。\n'
else
    printf '啟動失敗或逾時，請貼上本次輸出。\n'
    cat "$N6_LOGDIR/server_console.log"
    exit 1
fi

# 板端啟動成功後，才開始錄音接收。
printf '看到「錄音中」後，請說話約 5 秒。\n'

if python3 -u "$N6_RECEIVER" \
    2>&1 | tee "$N6_LOGDIR/receive.log"; then

    printf '錄音接收完成，請確認 WAV 路徑與播放結果。\n'
else
    printf '接收未完成，請貼上以下目錄的 start.log 與 receive.log：\n%s\n' "$N6_LOGDIR"
    exit 1
fi
