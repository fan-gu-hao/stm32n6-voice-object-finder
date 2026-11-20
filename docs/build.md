# 建置與外部依賴

[繁體中文](build.md) | [English](build.en.md)

已使用的環境為 GCC 14.3.1、ST Edge AI 4.0.1、ATON 1.1.3-275、`NetworkRuntime1201_CM55_GCC.a`、HAL 1.3.0 與 FreeRTOS 10.6.2。IDE 為 STM32CubeIDE 2.2.0。

本案核對的是 GCC 建置路徑：視覺參考工程的 Runtime1200 與正式手部底座的 Runtime1100，均在整合時配對至 GCC Runtime1201。`ai.mk` 保留的 IAR 設定仍指向 Runtime1100，未列為本案已完成的建置路徑。視覺產碼、記憶體區段及映像封裝的演進見[工程流程](engineering-workflow.md)與[原始歷程覆核](original-history-review.md)。

公開儲存庫保存應用程式、建置設定及訓練腳本。模型與預建映像未納入公開範圍，完整建置仍須具備對應版本的模型產碼與執行環境。不得將單獨下載公開儲存庫描述為可立即完成建置。

完整本機專案的模型位置為 `firmware/Model/` 與 `firmware/Model/kws/st_ai_output/`。實際編入清單以 `firmware/mks/ai.mk` 與 `firmware/mks/kws.mk` 為準。

在具備全部依賴的專案根目錄，可使用下列既有建置目標：

    bash firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh build_finder_ide/Project.elf build_finder_ide/Project.bin build_finder_ide/vision_commands.bin

建置腳本支援 `GCC_PATH` 指定編譯器目錄，或尋找本機 STM32CubeIDE 內的 GCC 14.3.1。IDE 建置路徑以專案所在位置解析。

這是流程文件；公開整理不會自動執行建置、產碼或燒錄。收音主機工具已放入 `kws/recording_tools/`，對應的 [FSBL 原始碼與 IDE 快照](../kws/recording_firmware/README.md)亦已公開；重建仍需固定版本 STM32CubeN6 SDK，並處理快照中的原開發路徑。主機工具需要對應的 ELF／BIN，沒有隨本庫附上預建映像。

[定版產碼與部署紀錄](evidence/development-history/README.md)保存命令、工具內部 ONNX、記憶體與執行階段報告、建置及成功寫入驗證，供追溯既有流程。
