# 視覺模型產碼與設定來源

[繁體中文](README.md) | [English](README.en.md)

本目錄補齊正式雙模型工程的視覺產碼入口與設定來源。2026-10-04 的開發紀錄確認：在本案 `vision/Model/` 執行官方腳本，使用 ST Edge AI 4.0.1 重新產生 N6 網路、權重與執行指令，再完成參考工程建置及正式韌體移植。模型來源與雜湊見 [sources.txt](../../sources.txt)。

## 三項官方參考原檔

下列三檔逐位元組取自官方實例分割範例的固定提交 `42f7d645f1ed61967a922defa4aa97b95d390b16`。它們保存原始命令及配置，沒有改寫成另一套產碼流程；來源網址、Git 物件雜湊、SHA-256 及大小見 [upstream-reference.json](upstream-reference.json)。

| 檔案 | 用途 |
| --- | --- |
| [產碼腳本](upstream-reference/generate-n6-model_STM32N6570-DK.sh) | 呼叫 `stedgeai generate`；複製網路、STAI 介面、執行階段控制器指令與權重；將權重轉為帶位址的 HEX |
| [Neural-ART 設定](upstream-reference/user_neuralart_STM32N6570-DK.json) | 選擇 `default` 配置、記憶體池與編譯選項，包含快取維護及執行階段控制器 |
| [記憶體池](upstream-reference/my_mpools/stm32n6-app2_STM32N6570-DK.mpool) | 提供編譯器可選的 SRAM、外部 RAM 及 Flash 位址、容量與存取屬性 |

這是**固定官方來源的參考快照**。目前沒有本機歷史腳本與這三檔的逐位元組比對紀錄，因此將其定位為上游參考，而非定版工作目錄的完整還原。它們也不包含模型權重、生成程式或預建映像。這三檔在官方來源中屬於 `Model`，元件授權索引列為 **SLA0044**；本目錄不改變其授權。參見 [vision/LICENSE.md](../LICENSE.md) 及[第三方來源聲明](../../THIRD_PARTY_NOTICES.md)。

## 本案使用的入口與產物交接

在具備模型、工具及原參考工程目錄結構的 `vision/Model/` 中，歷史產碼入口為：

```bash
bash generate-n6-model_STM32N6570-DK.sh
```

腳本內的核心命令為：

```bash
stedgeai generate --model yolov8n_256_quant_pc_ii_seg_coco-st.tflite --target stm32n6 --st-neural-art default@user_neuralart_STM32N6570-DK.json --input-data-type uint8
```

原腳本從搜尋路徑（PATH）取得 `stedgeai` 與 `arm-none-eabi-objcopy`，不會自行固定工具版本。此處保留原文，使用時須先確認選用版本與相依目錄；`upstream-reference/` 是閱讀快照，不能只靠這三檔重建整個模型。

正式工程移植六項模型產物：`network.c`、`network.h`、`network_ecblobs.h`、`stai_network.c`、`stai_network.h` 與 `network_data.xSPI2.bin`。其中官方這版腳本的複製清單沒有 `network.h`，所以完整產物交接仍須核對該標頭，不能只依腳本列出的複製項目推定齊全。

原官方參考工程的工具說明／GCC 函式庫與本案實際使用的新版產碼存在版本差異；本案將參考工程與正式底座的標頭、函式庫及 NPU 支援來源配對到 GCC Runtime1201。具體官方檔案、版本差異、修正與成功建置／部署證據見[工具鏈相容性](../../docs/toolchain-compatibility.md)。

## 記憶體池與最終雙模型配置的分工

**記憶體池描述編譯器可用的候選範圍，不等於最終模型實際占用，也不取代主應用的連結腳本。**

| 官方候選池 | 起點 | 容量 | 在雙模型工程的解讀 |
| --- | --- | --- | --- |
| `cpuRAM2` | `0x34100000` | 1,024 KiB | 視覺產碼可配置的片上區域；主應用 SRAM 結束於此位址之前 |
| `npuRAM3–6` | `0x34200000`、`0x34270000`、`0x342E0000`、`0x34350000` | 各 448 KiB | 各池是否使用、實際使用量由對應產碼結果判定 |
| `hyperRAM` | `0x90000000` | 16 MiB | 視覺產碼的外部工作區候選範圍 |
| `octoFlash` | `0x70380000` | 16 MiB | 原單視覺參考配置的權重候選範圍，不能直接視為雙模型可自由占用的容量 |

最終雙模型另外在 `0x70700000` 保留 KWS 權重區。它位於原官方 `octoFlash` 候選範圍內；因此 **YOLO 權重與 KWS 起點之間的可用間隔只有 `0x380000`，即 3.5 MiB**。重新產碼或更換模型時，必須以實際權重映像的起點與大小核對是否跨入 KWS 區，而不是沿用原候選池的 16 MiB 容量判定安全。

應用 SRAM、顯示／後處理 PSRAM、KWS 專用 RAM 與獨立視覺指令區由[正式連結腳本](../../firmware/Gcc/STM32N657xx.ld)、[KWS 記憶體池](../../kws/deployment/kws.mpool)及部署映像配置共同約束。各區段位址、保留容量、已保存的實際用量與五份映像分工見[雙模型記憶體配置](../../docs/memory-deployment.md)。
