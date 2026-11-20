from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
camera = fw / "Src/app_cam.c"
linker = fw / "Gcc/STM32N657xx.ld"
makefile = fw / "Makefile"
changes = {}

text = camera.read_text(encoding="utf-8")
if "FINDER_SQUARE_CAMERA_V1" not in text:
    start = "static void DCMIPP_PipeInitNn("
    end = "static void DCMIPP_IpPlugInit("

    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit("攝影機函式位置不同，尚未修改。")
    if text.count('#include "stai_palm_detector.h"') != 1:
        raise SystemExit("攝影機模型標頭與預期不同，尚未修改。")

    text = text.replace(
        '#include "stai_palm_detector.h"',
        '#include "stai_network.h"', 1
    )
    a, b = text.index(start), text.index(end)

    text = text[:a] + r'''/* FINDER_SQUARE_CAMERA_V1 */
static void DCMIPP_PipeInitNn(int sensor_width, int sensor_height)
{
  CMW_DCMIPP_Conf_t conf = {0};
  uint32_t pitch;

  conf.output_width = STAI_NETWORK_IN_1_WIDTH;
  conf.output_height = STAI_NETWORK_IN_1_HEIGHT;
  conf.output_format = NN_FORMAT;
  conf.output_bpp = STAI_NETWORK_IN_1_CHANNEL;
  conf.mode = CMW_Aspect_ratio_manual_roi;
  conf.enable_swap = 1;
  conf.enable_gamma_conversion = 0;

  CAM_InitCropConfig(&conf.manual_conf, sensor_width, sensor_height);
  assert(conf.manual_conf.width >= conf.manual_conf.height);
  conf.manual_conf.offset_x +=
      (conf.manual_conf.width - conf.manual_conf.height) / 2;
  conf.manual_conf.width = conf.manual_conf.height;

  int ret = CMW_CAMERA_SetPipeConfig(DCMIPP_PIPE2, &conf, &pitch);
  assert(ret == HAL_OK);
  assert(pitch == conf.output_width * conf.output_bpp);
}

''' + text[b:]
    changes[camera] = text

text = linker.read_text(encoding="utf-8")
if "FINDER_MEMORY_LAYOUT_V1" not in text:
    old = "AXISRAM1_2_S (xrw) : ORIGIN = 0x34000400, LENGTH =  1535K"

    if text.count(old) != 1 or text.count("  .psram_section (NOLOAD):") != 1:
        raise SystemExit("連結腳本配置與預期不同，尚未修改。")

    text = text.replace(
        old,
        "AXISRAM1_2_S (xrw) : ORIGIN = 0x34000400, LENGTH = 1023K\n"
        "  FLASH (rx) : ORIGIN = 0x71380000, LENGTH = 2M",
        1,
    )

    section = '''  /* FINDER_MEMORY_LAYOUT_V1 */
  .flash_section :
  {
    . = ALIGN(32);
    *(.flash_blob)
    *(.flash_blob.*)
    . = ALIGN(32);
  } >FLASH

'''
    text = text.replace(
        "  .psram_section (NOLOAD):",
        section + "  .psram_section (NOLOAD):", 1
    )
    changes[linker] = text

text = makefile.read_text(encoding="utf-8")
if "# FINDER_MEMORY_PLACEMENT_V1" not in text:
    anchor = "# C defines\n"
    if text.count(anchor) != 1:
        raise SystemExit("找不到 Makefile 的定義位置，尚未修改。")

    definitions = '''# FINDER_MEMORY_PLACEMENT_V1
C_DEFS += '-DECBLOB_CONST_SECTION=__attribute__((section(".flash_blob")))'
C_DEFS += '-DPOSTPROCESS_WRAPPER_SECTION=__attribute__((section(".psram_bss")))'
'''
    text = text.replace(anchor, anchor + definitions, 1)

    # 主程式與快閃記憶體命令分開輸出，避免巨大空洞映像。
    old_rule = "\t$($(quiet)BIN) $< $@"
    if text.count(old_rule) != 1:
        raise SystemExit("找不到 Makefile 的二進位輸出規則，尚未修改。")

    text = text.replace(
        old_rule,
        "\t$($(quiet)BIN) --remove-section=.flash_section $< $@",
        1,
    )
    text += '''
all: $(BUILD_DIR)/vision_commands.bin
$(BUILD_DIR)/vision_commands.bin: $(BUILD_DIR)/$(TARGET).elf
\t$($(quiet)BIN) --only-section=.flash_section $< $@
'''
    changes[makefile] = text

if changes:
    backup = root / "backups" / datetime.now().strftime(
        "vision_layout_%Y%m%d_%H%M%S_%f"
    )
    for path in changes:
        saved = backup / path.relative_to(fw)
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)

    for path, content in changes.items():
        path.write_text(content, encoding="utf-8")
        print("已修改：", path.relative_to(fw))

    print("備份：", backup)
else:
    print("攝影機與記憶體配置已完成，請繼續編譯。")
