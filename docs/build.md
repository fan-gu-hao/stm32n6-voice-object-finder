# 建置與外部依賴

[繁體中文](build.md) | [English](build.en.md)

已使用的環境為 GCC 14.3.1、ST Edge AI 4.0.1、ATON 1.1.3-275、`NetworkRuntime1201_CM55_GCC.a`、HAL 1.3.0 與 FreeRTOS 10.6.2。IDE 為 STM32CubeIDE 2.2.0。

**本案已完成官方範例版本對齊、記憶體配置與開機映像對齊修正。** [工具鏈相容性](toolchain-compatibility.md)逐項連到官方固定版本的原始設定、建置差異，以及本案成功建置、寫入與板端操作的紀錄；[雙模型記憶體與部署](memory-deployment.md)區分模型池、連結區段、儲存位址與執行位址。

本案核對的是 GCC 建置路徑：視覺參考工程的 Runtime1200 與正式手部底座的 Runtime1100，均在整合時配對至 GCC Runtime1201。`ai.mk` 保留的 IAR 設定仍指向 Runtime1100，未列為本案已完成的建置路徑。視覺產碼、記憶體區段及映像封裝的演進見[工程流程](engineering-workflow.md)與[原始歷程覆核](original-history-review.md)。

公開儲存庫保存應用程式、建置設定及訓練腳本。模型與預建映像未納入公開範圍，完整建置仍須具備對應版本的模型產碼與執行環境。

完整本機專案的模型位置為 `firmware/Model/` 與 `firmware/Model/kws/st_ai_output/`。實際編入清單以 `firmware/mks/ai.mk` 與 `firmware/mks/kws.mk` 為準。

在具備全部依賴的專案根目錄，可使用下列既有建置目標：

```bash
bash firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh \
  build_finder_ide/Project.elf \
  build_finder_ide/Project.bin \
  build_finder_ide/vision_commands.bin
```

| 輸出 | 用途 |
| --- | --- |
| `firmware/build_finder_ide/Project.elf` | 完整連結結果，供區段、符號與記憶體配置核對 |
| `firmware/build_finder_ide/Project.bin` | 排除 `.flash_section` 的應用映像，仍須開機標頭封裝 |
| `firmware/build_finder_ide/vision_commands.bin` | 僅含 `.flash_section`，部署至 `0x71380000` |

Makefile 的 `TX_MAX_PARALLEL_NETWORKS=1` 限制同時執行數量；YOLO 與 KWS 都已連入工程，由同一推論工作依序使用 NPU。上述編譯入口不自動封裝或燒錄。

建置腳本支援 `GCC_PATH` 指定編譯器目錄，或尋找本機 STM32CubeIDE 內的 GCC 14.3.1。IDE 建置路徑以專案所在位置解析。

視覺模型的腳本與設定入口見[視覺產碼來源](../vision/deployment/README.md)，語音模型見[KWS 產碼設定](../kws/deployment/README.md)。模型重新產碼後，需同步配對執行環境及 KWS 特徵／量化係數，並按實際映像範圍核對記憶體配置。上游視覺 Flash 候選池的容量涵蓋本案 KWS 權重位置，因此不能直接把候選池容量當作雙模型可用權重上限。

收音主機工具已放入 `kws/recording_tools/`，對應的 [FSBL 原始碼與 IDE 快照](../kws/recording_firmware/README.md)亦已公開；重建仍需固定版本 STM32CubeN6 SDK，並處理快照中的原開發路徑。主機工具需要對應的 ELF／BIN，沒有隨本庫附上預建映像。

[定版產碼與部署紀錄](evidence/development-history/README.md)保存命令、工具內部 ONNX、記憶體與執行階段報告、建置及成功寫入驗證，供追溯既有流程。
