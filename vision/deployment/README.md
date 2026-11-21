# 視覺模型匯出、量化、N6 產碼與部署

[繁體中文](README.md) | [English](README.en.md)

> **版本編號說明：**`Runtime1100`、`Runtime1200`、`Runtime1201` 分別代表 ST 神經網路執行函式庫（Network Runtime）的 **11.0.0、12.0.0、12.0.1** 版本。這套函式庫在建置時連結進韌體，提供模型程式所需的執行支援；更新模型產碼工具時，也須配對函式庫、標頭檔與神經網路處理器（NPU）支援程式。這些編號與 ST Edge AI 工具本身的版本號分開記錄。 [版本配對詳解](../../docs/toolchain-compatibility.md)。

本作品的視覺開發從 Python／PyTorch 模型處理開始，涵蓋 ONNX 匯出、TensorFlow SavedModel 轉換、逐通道 INT8 量化、介面核對及 ST Edge AI／Neural-ART 產碼。作者親自執行各階段，再將網路程式、介面、權重與執行指令接入雙模型主應用，完成執行期配對、建置與映像封裝。

本頁對應[完整開發步驟第3步：視覺模型轉換](../../docs/development-steps.md#step-03)，說明產碼輸入、工具處理、產物用途及韌體交接；工具版本差異見[工具鏈相容性](../../docs/toolchain-compatibility.md)，位址與映像配置見[雙模型記憶體配置](../../docs/memory-deployment.md)。

## 從 Python／PyTorch 到 N6 的完整視覺開發流程

**Python／PyTorch（`.pt`）→ ONNX → TensorFlow SavedModel → 逐通道 INT8 量化（TFLite）→ ST Edge AI／Neural-ART → N6 網路與介面（C／H）、權重（BIN）及執行指令。** 作者親自完成模型匯出、格式轉換、量化校正、介面核對與 N6 產碼，再把模型接入雙模型韌體。模型前段的實作與紀錄保存於視覺工程，正式韌體整合則保存於本儲存庫。

| 階段 | 作者實際完成的工作 | 程式、設定與成功紀錄 |
| --- | --- | --- |
| Python／PyTorch 模型匯出 | 以 Python／Ultralytics 工具載入本地 `yolov8n-seg.pt`，配置 256×256 輸入，匯出 ONNX；日誌記錄 opset 19、圖簡化及匯出成功 | [模型匯出日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log) |
| ONNX 轉 TensorFlow | 透過 `onnx2tf` 將 ONNX 轉成 TensorFlow SavedModel，保留偵測與遮罩原型兩組輸出，接續 TFLite 匯出 | [ONNX／SavedModel 成功紀錄](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log) |
| 自行執行 INT8 量化 | 以本地 SavedModel 與校正影像執行 ST 量化工具，設定逐通道量化、影像縮放及 INT8 輸入輸出，產生量化 TFLite | [量化設定](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/configs/yolov8n_seg_int8_int8.yaml)、[量化成功日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/04_st_quantization_seg.log) |
| 電腦端與部署介面核對 | 比較原始、浮點與 INT8 模型；核對輸入輸出形狀、張量型別、尺度、零點與 N6 後處理介面 | [電腦端模型比較](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/scripts/check_seg_models_pc.sh)、[N6 介面檢查](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/scripts/check_n6_seg_header.py) |
| N6 產碼與正式韌體接入 | 使用 ST Edge AI／Neural-ART 產生網路、STAI 介面、權重與視覺執行指令；配對執行函式庫，更新建置、記憶體、後處理及顯示 | [視覺模型部署程式](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/scripts/deploy_n6_seg.sh)、[雙模型工程產碼流程](../../tools/development-history/vision_03_generate_and_build_vision.sh)、[六項產物移植](../../tools/development-history/vision_05_copy_vision_artifacts.sh) |

模型匯出、量化與雙模型整合分階段保存版本；下方來源表對應特定 N6 產碼批次的輸入檔。完整開發工作由上述程式、設定與成功日誌共同追溯，模型及權重的位元組版本則依各批次雜湊辨識。

## 三項官方參考原檔

下列三檔逐位元組取自官方實例分割範例的固定提交 `42f7d645f1ed61967a922defa4aa97b95d390b16`。它們保存原始命令及配置，沒有改寫成另一套產碼流程；來源網址、Git 物件雜湊、SHA-256 及大小見 [upstream-reference.json](upstream-reference.json)。

| 檔案 | 用途 |
| --- | --- |
| [產碼腳本](upstream-reference/generate-n6-model_STM32N6570-DK.sh) | 呼叫 `stedgeai generate`；複製網路、STAI 介面、執行階段控制器指令與權重；將權重轉為帶位址的 HEX |
| [Neural-ART 設定](upstream-reference/user_neuralart_STM32N6570-DK.json) | 選擇 `default` 配置、記憶體池與編譯選項，包含快取維護及執行階段控制器 |
| [記憶體池](upstream-reference/my_mpools/stm32n6-app2_STM32N6570-DK.mpool) | 提供編譯器可選的 SRAM、外部 RAM 及 Flash 位址、容量與存取屬性 |

這是**固定官方來源的參考快照**。目前沒有本機歷史腳本與這三檔的逐位元組比對紀錄，因此將其定位為上游參考，而非定版工作目錄的完整還原。它們也不包含模型權重、生成程式或預建映像。這三檔在官方來源中屬於 `Model`，元件授權索引列為 **SLA0044**；本目錄不改變其授權。參見 [vision/LICENSE.md](../LICENSE.md) 及[第三方來源聲明](../../THIRD_PARTY_NOTICES.md)。

## 雙模型工程的 N6 產碼與產物交接

| 階段 | 本案實際處理 |
| --- | --- |
| 準備產碼輸入 | 核對本地 TFLite 模型、Neural-ART 設定及記憶體池；選用 ST Edge AI Core `4.0.1-20581`，工具同時回報 STM32CubeAI `12.0.1-RC2` |
| 轉為 N6 部署產物 | 在 `vision/Model/` 執行產碼腳本，以 `--target stm32n6`、`default` 設定及 `--input-data-type uint8` 產生配合相機輸入的 N6 模型介面；設定涵蓋模型記憶體配置、快取維護與執行階段控制器 |
| 整理網路與資料 | 取得 `network.c/.h`、`stai_network.c/.h`、`network_ecblobs.h` 與 `network_data.xSPI2.bin`，分別提供網路執行程式、STAI 呼叫介面、執行指令與權重 |
| 配對執行期 | 視覺參考工程由 Runtime1200、正式主工程由 Runtime1100 配對至 `NetworkRuntime1201_CM55_GCC.a`，同步更新標頭、函式庫及 NPU 支援來源 |
| 接入正式韌體 | 將六項產物複製至 `firmware/Model/`，修改建置清單及模型呼叫，接入實例分割後處理、相機輸入、目標搜尋與顯示資料流 |
| 建置與映像輸出 | 完成正式主工程 ELF 連結；從 `.flash_section` 分離視覺指令，保留應用、權重及指令各自的部署位置，再進行開機標頭封裝 |

模型檔取得之後，還需完成上述轉換、執行期配置、韌體整合及映像準備，才能進入板端部署。各步驟的產物和完成紀錄分別保存。

### 本案實際執行的主機流程原碼

開發時的 14 份視覺主機流程已收錄於[開發原碼目錄](../../tools/development-history/README.md)，包括工程建立、模型產碼、執行期更新、後處理移植、相機／記憶體配置與正式建置。可直接從下列入口閱讀本案的操作與修改：

- [執行產碼與參考工程建置](../../tools/development-history/vision_03_generate_and_build_vision.sh)、[視覺執行期配對](../../tools/development-history/vision_02_match_vision_runtime.py)。
- [六項模型產物複製](../../tools/development-history/vision_05_copy_vision_artifacts.sh)、[正式韌體執行期配對](../../tools/development-history/vision_06_match_main_runtime.py)。
- [後處理來源移植](../../tools/development-history/vision_08_import_postprocessing.py)、[搜尋應用與中斷介面整合](../../tools/development-history/vision_12_integrate_vision_application.py)。
- [相機與記憶體配置修改](../../tools/development-history/vision_13_configure_camera_and_memory.py)、[正式主工程建置與映像輸出](../../tools/development-history/vision_14_build_main_vision.py)。

這些檔案保存當時完整的終端機程式區塊；逐檔用途、完成狀態與原始／公開雜湊見[來源紀錄](../../tools/development-history/source-provenance.json)。定版韌體保留在 `firmware/`，歷史流程另行保存以呈現實作過程。

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

### 2026-10-04 的實際完成紀錄

| 輸出階段 | 當時保存的結果 |
| --- | --- |
| `vision_20261004_181810` | 終端輸出確認模型產碼完成、參考工程 ELF 連結及開機映像封裝成功；應用 SRAM 352,320 B、視覺指令230,528 B、PSRAM 2,404,512 B |
| 六項產物交接 | 終端逐項列出從 `vision/Model/STM32N6570-DK/` 複製到 `firmware/Model/` 的網路程式、標頭、STAI 介面、指令與權重 |
| `finder_vision_20261004_193031_265404` | 正式主工程建置成功；應用 SRAM 351,240 B、視覺指令230,528 B、PSRAM 8,949,920 B。視覺權重映像3,474,865 B，置於 `0x70380000`；視覺指令置於 `0x71380000` |

這兩次建置分別對應參考工程與移植後的視覺主工程，當時尚未加入 KWS。[原始歷程覆核](../../docs/original-history-review.md)記錄執行順序，[映像配置節錄](../../docs/evidence/development-history/vision_image_layout_20261004.txt)保存正式視覺版的映像大小與位址。後續雙模型的完整用量與部署結果見[記憶體配置](../../docs/memory-deployment.md)及[結果](../../docs/results.md)。

### 10月4日產碼輸入來源紀錄

[sources.txt](../../sources.txt)是在當時取得模型後，以 `sha256sum` 讀取本地檔案建立的來源紀錄。它定位該次產碼輸入的固定來源與內容雜湊：

| 欄位 | 保存內容 |
| --- | --- |
| 模型檔 | `yolov8n_256_quant_pc_ii_seg_coco-st.tflite` |
| 來源版本 | `stm32-hotspot/ultralytics` 提交 `176ecaa749b79a3f53ce077d2b14412fa45e81a0` |
| 本地路徑 | `vision/Model/yolov8n_256_quant_pc_ii_seg_coco-st.tflite` |
| SHA-256 | `3316733125a5fb85d66ed33993627b5d293b3baceb348b137132071ca365ebd6` |

原始取得流程另以 Git 物件雜湊核對檔案；使用者終端回貼確認模型大小為3,514,494 B。之後的產碼完成、產物複製與正式主工程建置由上表的執行輸出對應。來源紀錄、生成產物與部署映像各自保存，方便追溯這條轉換與整合流程。

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
