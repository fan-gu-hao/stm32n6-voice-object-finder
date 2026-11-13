# 建置與外部依賴

已使用的環境為 GCC 14.3.1、ST Edge AI 4.0.1、ATON 1.1.3-275、`NetworkRuntime1201_CM55_GCC.a`、HAL 1.3.0 與 FreeRTOS 10.6.2。IDE 為 STM32CubeIDE 2.2.0。

公開儲存庫保存應用程式、建置設定及訓練腳本。模型與預建映像未納入公開範圍，完整建置仍須具備對應版本的模型產碼與執行環境。不得將單獨下載公開儲存庫描述為可立即完成建置。

完整本機專案的模型位置為 `firmware/Model/` 與 `firmware/Model/kws/st_ai_output/`。實際編入清單以 `firmware/mks/ai.mk` 與 `firmware/mks/kws.mk` 為準。

在具備全部依賴的專案根目錄，可使用下列既有建置目標：

    bash firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh build_finder_ide/Project.elf build_finder_ide/Project.bin build_finder_ide/vision_commands.bin

建置腳本支援 `GCC_PATH` 指定編譯器目錄，或尋找本機 STM32CubeIDE 內的 GCC 14.3.1。IDE 建置路徑以專案所在位置解析。

這是流程文件；公開整理不會自動執行建置、產碼或燒錄。收音主機工具已放入 `kws/recording_tools/`；仍需外部收音專案的對應韌體，詳見 [收音工具說明](../kws/recording_tools/README.md)。
