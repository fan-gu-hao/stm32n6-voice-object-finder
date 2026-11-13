# KWS 模型與前處理
KWS_MODEL_DIR := Model/kws/st_ai_output
KWS_DSP_DIR := STM32Cube_FW_N6/Drivers/CMSIS/DSP
C_SOURCES += Src/finder_kws.c
C_SOURCES += $(KWS_MODEL_DIR)/kws_network.c
C_SOURCES += $(KWS_MODEL_DIR)/stai_kws_network.c
C_INCLUDES += -I$(KWS_MODEL_DIR)
C_INCLUDES += -I$(KWS_DSP_DIR)/Include
C_INCLUDES += -I$(KWS_DSP_DIR)/PrivateInclude
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/TransformFunctions/arm_rfft_fast_f32.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/TransformFunctions/arm_rfft_fast_init_f32.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/TransformFunctions/arm_cfft_f32.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/TransformFunctions/arm_cfft_init_f32.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/TransformFunctions/arm_cfft_radix8_f32.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/TransformFunctions/arm_bitreversal2.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/CommonTables/arm_common_tables.c
KWS_DSP_SOURCES += $(KWS_DSP_DIR)/Source/CommonTables/arm_const_structs.c
C_SOURCES += $(KWS_DSP_SOURCES)

# 這組 FFT 採用 CMSIS-DSP 的標量實作，所有相關檔案保持相同設定。
KWS_DSP_OBJECTS := $(addprefix $(BUILD_DIR)/,$(KWS_DSP_SOURCES:.c=.o))
$(KWS_DSP_OBJECTS) $(BUILD_DIR)/Src/finder_kws.o: CFLAGS += -DARM_MATH_AUTOVECTORIZE

# FINDER_MIC_LIVE_V1
C_SOURCES += Src/finder_mic.c
C_SOURCES += STM32Cube_FW_N6/Drivers/STM32N6xx_HAL_Driver/Src/stm32n6xx_hal_mdf.c
