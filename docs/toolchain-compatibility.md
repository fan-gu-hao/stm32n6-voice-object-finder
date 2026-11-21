# 工具鏈相容性、建置差異與部署修正

[繁體中文](toolchain-compatibility.md) | [English](toolchain-compatibility.en.md)

## 先看懂版本編號：1100、1200、1201 是什麼？

本文的「執行期（Runtime）」版本縮寫，指 ST 提供的**神經網路執行函式庫（Network Runtime）**。模型轉換工具產生的程式需要配合這套函式庫；建置時將所需函式連結進韌體，供板端推論使用。

| 本文縮寫 | 函式庫版本 | 本案中的位置 |
| --- | --- | --- |
| `Runtime1100` | **11.0.0** | 官方手部雙模型底座原本使用的版本 |
| `Runtime1200` | **12.0.0** | 官方視覺參考工程原本使用的版本 |
| `Runtime1201` | **12.0.1** | 本案 GCC 建置整合後使用的版本 |

例如 `NetworkRuntime1201_CM55_GCC.a` 表示：**12.0.1 版神經網路執行函式庫、適用於 Cortex-M55、供 GCC 工具鏈連結的靜態函式庫（`.a`）**。目前的[版本標頭](../firmware/Lib/AI_Runtime/Inc/core_datatypes.h)明確定義 12／0／1，[連結設定](../firmware/mks/ai.mk)則選用這份函式庫。

更新模型產碼工具後，產生的程式可能需要新版介面或行為，因此本案同步更新函式庫、標頭檔與 NPU 支援程式，使模型程式與韌體配套一致。**ST Edge AI Core 4.0.1 是產碼工具版本；Network Runtime 12.0.1 是函式庫版本**；Neural-ART 支援元件另有自己的版本紀錄，分別見下表。

本案將兩份不同工具版本的官方工程，整合到 GCC 14.3.1、ST Edge AI 4.0.1 與 Runtime1201 的同一套建置流程。工作包括辨識產碼與執行期的版本差異、移植記憶體區段設定、分開輸出映像，以及排查寫入成功後仍無法正常啟動的封裝問題。

## 固定來源與版本配對

| 工程／階段 | 官方固定版本的原設定 | 本案採用方式 |
| --- | --- | --- |
| 視覺參考工程 | 實例分割範例 `42f7d645f1ed61967a922defa4aa97b95d390b16`；README 列 ST Edge AI 4.0.0，Makefile 連結 Runtime1200 | 在本案 `vision/` 以 ST Edge AI 4.0.1 重新產碼，更新為 GCC Runtime1201 |
| 正式主工程底座 | 手部雙模型範例 `6c313001f69d3ddb1ffa7bd700aba74f9c11037b`（v2.2.0）；README 列 ST Edge AI 3.0.0，`mks/ai.mk` 連結 Runtime1100 | 換入 YOLO 與 KWS，統一 GCC Runtime1201，保留 FreeRTOS 抽象層與非同步執行模式 |
| 本案實際環境 | STM32CubeIDE 2.2.0、GCC 14.3.1、ST Edge AI Core 4.0.1-20581、Neural-ART／ATON 1.1.3-275、CubeProgrammer／Signing Tool 2.23.0 | 模型產碼、標頭、函式庫、NPU 支援來源及連結設定一起配對 |

官方原設定可直接核對：分割範例的 [README 第112–116行][v-tools]、[Makefile 第219行][v-runtime]，以及手部範例的 [README 第59–63行][h-tools]、[`ai.mk` 第46–47行][h-runtime]。兩份 README 都說明更換 ST Edge AI 版本時，可能遇到 `Possible mismatch in ll_aton library used`，並要求更新執行期（[分割範例][v-migration]、[手部範例][h-migration]）。

因此，這裡的 Runtime1200／1100 並不是在原配套下錯誤的設定；它們與本案選用的新版產碼環境不同。正式 course17 紀錄保存了版本對齊後的成功建置；上述警告是官方列出的相容性風險，並非本案留存的錯誤輸出。

## 產碼指令與執行期更新

固定版本的[官方視覺產碼腳本][v-generate]第5行直接呼叫環境搜尋路徑（PATH）中的 `stedgeai`，沒有在腳本內鎖定工具版本。第7–11行複製網路程式、STAI 介面、執行指令及權重，第12行另呼叫 PATH 中的 `arm-none-eabi-objcopy`，將權重轉為指定外部 Flash 位址的 HEX。

本案先將 ST Edge AI 4.0.1 與選定 GCC 工具目錄加入 PATH，再執行此產碼流程；更新內容不是只更改一個函式庫名稱：

1. 視覺參考工程更新 `Middlewares/stedgeai-lib/Inc`、`Lib`、`Npu`，並將 GCC 連結項目由 Runtime1200 改成 Runtime1201。
2. 正式手部底座更新 `firmware/Lib/AI_Runtime/Inc`、`Lib`、`Npu`，將 `firmware/mks/ai.mk` 的 GCC 連結項目由 Runtime1100 改成 `NetworkRuntime1201_CM55_GCC.a`。
3. 將本案產生的 YOLO 網路程式與權重移入 `firmware/Model/`，調整建置清單及模型呼叫；KWS 使用獨立網路名稱，之後以相同工具鏈產碼並共同連結。

2026-10-04 原始終端紀錄確認視覺產碼、執行期更新及建置完成；2026-10-08 的 [KWS 產碼報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)也直接記錄工具 4.0.1、編譯器 1.1.3-275 與 `NetworkRuntime1201_CM55_GCC.a`。視覺來源及產碼入口另見[視覺部署說明](../vision/deployment/README.md)。

## 建置入口與記憶體區段的差異

| 固定官方來源中的差異 | 本案的整合處理 | 技術意義 |
| --- | --- | --- |
| 分割範例的 CubeIDE `ModelZoo` 組態已有 `.flash_blob`／`.psram_bss` 編譯定義（[第136、163–164行][v-cproject]）；同版獨立 Makefile 沒有這兩項定義 | 在本案 Makefile 明確加入 `ECBLOB_CONST_SECTION` 與 `POSTPROCESS_WRAPPER_SECTION`，將視覺指令放入 Flash、後處理緩衝放入 PSRAM | 不同建置組態不會自動繼承彼此的記憶體配置 |
| 分割範例連結腳本已有 `.flash_section` 與 PSRAM 區段（[第152–164行][v-sections]）；手部底座只有1535 KiB應用 SRAM與既有 PSRAM 區段（[第14–19行][h-memory]） | 正式工程將應用 SRAM 改為1023 KiB，新增 `0x71380000`／2 MiB視覺指令區，保留 PSRAM 區段並加入本案後處理配置 | 模型記憶體池與完整應用連結配置一起調整，避免應用區域跨入視覺活化值區 |
| 原 Makefile 直接把整份 ELF 轉成 BIN（[分割範例第264–265行][v-binary]、[手部範例第198–199行][h-binary]） | 正式工程分別排除／只取 `.flash_section`，輸出應用與 `vision_commands.bin` | 新增分離的外部 Flash 區段後，也必須同步修改映像抽取方式，避免位址空洞膨脹二進位檔 |

這些是具體建置路徑與新模型記憶體配置的適配工作。正式 course17 在完成配置後成功建置；早期另一個影音嘗試的 SRAM 溢位不列為這個正式工程的失敗紀錄。

## 封裝規則不一致與本案啟動修正

同一個分割範例提交存在可核對的封裝入口差異：[README 第297–306行][v-align]區分 CubeProgrammer 2.21 前後，要求2.21以上加入 `--align`；但 [Makefile 第267–268行][v-sign]的封裝規則仍未帶對齊選項。手部底座的[封裝範例第195行][h-sign]也沒有該選項，而它的版本表是 CubeProgrammer 2.18.0。這表示使用本案的2.23.0工具時，必須選用相應版本的封裝規則，不能直接混用不同入口的命令。

本案10月4日的視覺映像已成功使用 `0x400` 對齊。後來10月6日組合即時語音版的本地封裝指令時，遺漏了既有成功配置中的對齊選項；這是本案整合流程的回歸，不能全部歸因於官方工程。

| 實際觀察與檢查 | 修正及結果 |
| --- | --- |
| 應用與 KWS 權重寫入、驗證成功後，使用者仍回報黑畫面，沒有正常啟動輸出 | 進一步核對 CPU 狀態、ELF 向量／符號，以及封裝內的原始程式位置，區分「Flash 寫入正確」與「映像可正確啟動」 |
| 原始 BIN 在封裝檔中的偏移為 `0x240`；程式內容逐位元組相同 | 恢復已採用的無金鑰封裝設定，包含 `-of 0x80000000` 與 `-align`；重新檢查有效負載偏移為 `0x400`，內容仍與原始 BIN 完全相同 |
| 修正後出現 KWS 串列輸出，後續雙模型除錯及操作得以繼續 | 保留為已確認的封裝缺陷與修正證據；沒有把它擴大成所有黑畫面、核心錯誤或辨識錯誤的唯一根因 |

這段除錯的原始執行結果與時間順序見[原始歷程覆核](original-history-review.md)。`-nk` 為無金鑰模式，這裡的動作稱為加入開機標頭及對齊封裝，不宣稱提供密碼學簽章。

## 現行 GCC 建置入口

在具備對應模型產碼與執行環境的完整專案根目錄，現行入口為：

```bash
bash firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh \
  build_finder_ide/Project.elf \
  build_finder_ide/Project.bin \
  build_finder_ide/vision_commands.bin
```

[`cubeide_make.sh`](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh)接受 `GCC_PATH`，或在本機 STM32CubeIDE 安裝中尋找 GCC 14.3.1，核對版本後把編譯器目錄加入 PATH；以腳本所在位置解析正式韌體目錄，交給 Make 產生上述三個目標。這個入口輸出 ELF、原始應用與視覺指令，不自動封裝或燒錄。完整依賴與模型位置見[建置說明](build.md)。

目前已確認的建置路徑為 GCC；`ai.mk` 保留的 IAR 設定仍指向 Runtime1100，沒有列為已完成驗證的路徑。

## 已保存的建置、部署與板端結果

| 階段 | 直接證據與結果 |
| --- | --- |
| 2026-10-04正式視覺版 | 原始終端紀錄中的 `finder_vision_20261004_193031_265404` 建置完成：SRAM 351,240 B、視覺指令230,528 B、PSRAM 8,949,920 B；[板端日誌](evidence/development-history/finder_vision_20261004.log)保存早期視覺 FOUND 結果 |
| 2026-10-08定版雙模型建置 | [原始建置日誌](evidence/development-history/deployment_20261008/build.log)記錄 SRAM 535,544 B／1023 KiB、視覺指令230,528 B／2 MiB、一般 PSRAM 8,949,920 B／16128 KiB。`KWS_RAM` 列為0 B是連結器統計，不代表固定配置的模型活化值沒有使用記憶體 |
| 定版映像更新 | [部署清單](evidence/development-history/deployment_20261008/flash_manifest.json)與[驗證紀錄](evidence/development-history/deployment_20261008/flash_verified.json)確認此次應用 `0x70100000`、KWS 權重 `0x70700000` 的寫入及驗證成功；其餘映像沿用已有配置 |
| 定版板端操作 | [10月8日日誌](evidence/development-history/voice_groupcv_20261008.log)保存 cup、bottle、phone各兩次正確接受；同輪視覺結果皆為 found=0，因此與10月4日視覺 FOUND 分開記錄 |

現行建置入口是公開整理後的入口；上述成功結果來自保留的歷史建置與硬體紀錄，本次文件整理未重跑建置或燒錄。[實機展示影片](https://youtu.be/m7wET9g5u6k)已提供；最終雙模型的獨立供電／冷啟動仍待核對，完整結果見[結果說明](results.md)。

[v-tools]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/README.md#L112-L116
[v-runtime]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/Makefile#L219
[h-tools]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/README.md#L59-L63
[h-runtime]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/mks/ai.mk#L46-L47
[v-migration]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/README.md#L347-L354
[h-migration]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/README.md#L220-L227
[v-generate]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Model/generate-n6-model_STM32N6570-DK.sh#L3-L12
[v-cproject]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/STM32CubeIDE/.cproject#L136-L164
[v-sections]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/STM32CubeIDE/STM32N657xx.ld#L152-L164
[h-memory]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/Gcc/STM32N657xx.ld#L14-L19
[v-binary]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/Makefile#L264-L265
[h-binary]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/Makefile#L198-L199
[v-align]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/README.md#L297-L306
[v-sign]: https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/Makefile#L267-L268
[h-sign]: https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/README.md#L191-L196
