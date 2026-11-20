from pathlib import Path
import struct
import subprocess

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
elf = root / "firmware/build_finder_kws/Project.elf"
ide = Path("/opt/st/stm32cubeide_2.2.0")

matches = list(ide.glob(
    "plugins/com.st.stm32cube.ide.mcu.externaltools."
    "gnu-tools-for-stm32.*/tools/bin/arm-none-eabi-addr2line"
))
if len(matches) != 1 or not elf.is_file():
    raise SystemExit("找不到唯一的位址解析工具，或本次 ELF 不存在。")

tools = matches[0].parent

def read_tool(name, *args):
    return subprocess.check_output(
        [str(tools / ("arm-none-eabi-" + name)),
         *map(str, args)],
        text=True, stderr=subprocess.STDOUT
    )

print("使用編譯檔：", elf)

print("\n【返回位址及其前方指令對應的原始碼】")
print(read_tool(
    "addr2line", "-e", elf, "-a", "-f", "-C", "-i",
    "0x34025786", "0x3402578a", "0x340256e0"
))

print("【啟動函式與堆疊符號】")
names = {
    "_estack", "_sstack", "Reset_Handler", "HardFault_Handler",
    "SystemInit", "__libc_init_array", "main", "g_pfnVectors"
}
for line in read_tool("nm", "-n", elf).splitlines():
    fields = line.split()
    if fields and fields[-1] in names:
        print(line)

print("\n【ELF 中斷向量表開頭】")
vectors = read_tool("objdump", "-s", "-j", ".isr_vector", elf)
print("\n".join(vectors.splitlines()[:10]))

print("\n【返回位址附近的組合語言】")
print(read_tool(
    "objdump", "-d",
    "--start-address=0x34025760",
    "--stop-address=0x340257b0", elf
))

pointer = root / "output/finder_voice_current.txt"
out = Path(pointer.read_text().strip())
raw = (out / "finder.bin").read_bytes()
signed = (out / "finder_signed.bin").read_bytes()

print("【本次燒錄映像】")
print("目錄：", out)
for label, value in zip(
    ("初始堆疊", "重設入口", "NMI 入口", "HardFault 入口"),
    struct.unpack_from("<4I", raw)
):
    print(f"{label}：0x{value:08X}")

offset = signed.find(raw[:64])
print("原始程式在簽章映像中的偏移：",
      hex(offset) if offset >= 0 else "找不到")
print("簽章映像內的程式內容完全一致：",
      offset >= 0 and signed[offset:offset + len(raw)] == raw)
