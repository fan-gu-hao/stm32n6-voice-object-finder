# 雙模型語音找物：從資料建立到 N6 部署

[繁體中文](engineering-workflow.md) | [English](engineering-workflow.en.md)

> **版本編號說明：**`Runtime1100`、`Runtime1200`、`Runtime1201` 分別代表 ST 神經網路執行函式庫（Network Runtime）的 **11.0.0、12.0.0、12.0.1** 版本。這套函式庫在建置時連結進韌體，提供模型程式所需的執行支援；更新模型產碼工具時，也須配對函式庫、標頭檔與神經網路處理器（NPU）支援程式。這些編號與 ST Edge AI 工具本身的版本號分開記錄。 [版本配對詳解](toolchain-compatibility.md)。

本專案在 STM32N6570-DK 上建立關鍵字辨識（Keyword Spotting，KWS）與 YOLOv8 實例分割的雙模型系統。工程流程涵蓋需求與工程建立、YOLO 模型轉換及韌體移植、攝影機／後處理／顯示整合、語音資料與梅爾頻率倒譜係數（MFCC）前處理、自行訓練及 INT8 量化 KWS、共享 NPU 的雙模型韌體、記憶體配置、數值除錯、定版部署與展示。

從功能定義到實機展示的逐項實作見[完整 32 步開發流程](development-steps.md)；每一步直接對應的程式、配置與紀錄見[原始碼對照清單](development-source-map.json)。本頁保留各階段的開發順序與模型整合、部署細節；開發時執行的主機比對、資料收集和部署程式見[歷史流程原始碼](../tools/development-history/README.md)。

視覺持續辨識攝影機畫面；語音命令 cup、bottle、phone 改變搜尋目標。兩個模型在同一推論工作中依序使用神經網路處理器（NPU），顯示與影像訊號處理（ISP）由另外兩個工作協作。[實作與證據索引](development-coverage.md)列出各步驟對應的程式、設定與結果。

記憶體配置與燒錄位置的完整對照見[雙模型記憶體與部署](memory-deployment.md)；官方範例版本、實際建置指令及封裝修正見[工具鏈相容性](toolchain-compatibility.md)。

## 開發順序與各階段成果

這個系統先完成視覺主工程，再加入自行蒐集資料的 KWS，最後處理即時辨識與部署問題。更早的視覺、收音工程及未採用嘗試，另見[原始歷程重建](original-history-review.md)；各階段的成果按當時工程與模型版本記錄。

| 開發階段 | 實際完成的工作 | 與定版的關係 |
| --- | --- | --- |
| 前置收音依賴 | 在 course15 建立 N6 收音韌體與主機接收工具 | course17 的資料蒐集沿用這套錄音入口；本庫後來納入實際依賴的收音來源與工具 |
| 視覺匯出、量化與產碼 | 親自將 PyTorch 模型經 ONNX 轉為 SavedModel，執行逐通道 INT8 量化與介面核對，再產生 N6 產物並整合至雙模型工程 | 涵蓋視覺模型準備與後續韌體產碼／建置，各階段程式與紀錄列於下方 |
| 正式主工程 | 以官方手部雙模型範例為 `firmware/` 底座，移入 YOLO 產碼，改接後處理、中央裁切、目標選擇、記憶體與工作間交接；完成視覺版建置與板端紀錄 | 完成正式主工程的視覺版；此階段尚未整合語音控制 |
| 資料與初版 KWS | 完成五分類錄音、切段、來源分組、MFCC、模型訓練與 INT8 匯出 | 保留初版訓練程式；與後來分組定版分開 |
| 語音核心與收音整合 | KWS 產碼、C 特徵與模型介面、專用記憶體、CMSIS-DSP 建置，接入連續 MDF／DMA 收音及語音接受狀態 | 從可建置核心進展到即時雙模型；編譯成功不等於辨識驗證完成 |
| 部署與數值除錯 | 排查黑畫面及核心錯誤，核對映像有效負載偏移並修復 `0x400` 對齊；再以固定特徵、同一 PCM 與現場視窗比較電腦／板端結果 | 保留映像封裝失敗、特徵與輸出比較，以及 silence 誤判為 phone 的結果，沒有將它們當成成功驗收 |
| 資料迭代與定版 | 加入現場資料、處理資料洩漏、五折分組驗證與保留評估，部署定版 KWS 並保存三個命令各兩次接受的日誌 | 對應下方驗證表；同輪視覺日誌為 found=0，早期視覺 FOUND 另有紀錄 |
| 定版後：工程交付 | 整理 IDE 來源入口、建置路徑、來源追溯、程式導覽、訓練與部署證據，公開可閱讀原始碼 | 展示影片及未實測項目保留明確狀態 |

## 功能定義、工程建立與模型分工

第 **1–2 步**先定義板端操作，再建立視覺參考、正式韌體及語音資料／訓練目錄。

| 階段 | 本專案完成的工作 | 實作入口 |
| --- | --- | --- |
| 功能需求與目錄建立 | 在 STM32N6570-DK 上完成語音與視覺推論，三個語音命令切換目標，LCD 顯示搜尋狀態、物件框與遮罩；將視覺參考、正式韌體及語音流程分為 `vision/`、`firmware/`、`kws/` | [系統架構](architecture.md)、[工程建立流程](../tools/development-history/vision_01_prepare_vision.sh) |
| 平台與應用框架 | 固定 GCC、ST Edge AI、Neural-ART 與執行期版本，將 ST 雙模型 FreeRTOS 框架改接語音與視覺模型 | [建置環境](build.md)、[來源紀錄](source-provenance.json)、[app.c](../firmware/Src/app.c) |
| 語音資料蒐集子系統 | MDF／DMA 五秒錄音、RAM 啟動、UART 交握及 CRC32、WAV 保存、分類收集與切段 | [錄音韌體](../kws/recording_firmware/README.md)、[主機工具](../kws/recording_tools/README.md)、[collect_n6.py](../kws/collect_n6.py) |
| KWS 模型建立 | 自行蒐集五分類資料、MFCC、深度可分離卷積、資料增強與分組交叉驗證，匯出 INT8 模型 | [訓練快照](../kws/training_snapshot/README.md)、[訓練演進](../kws/training_history/README.md) |
| 兩模型部署與整合 | 完成 YOLO 匯出、格式轉換及 INT8 量化，再執行 YOLOv8 與 KWS 的 N6 產碼，配對共用執行期、移植模型與後處理介面；配置兩模型記憶體、共享 NPU 排程及搜尋狀態 | [視覺部署](../vision/deployment/README.md)、[KWS 部署](../kws/deployment/README.md)、[app.c](../firmware/Src/app.c)、[連結腳本](../firmware/Gcc/STM32N657xx.ld) |

## 視覺產碼、韌體移植與搜尋顯示的逐步工作

這一階段先完成可運作的視覺主工程，再接入語音模型；對應完整開發流程第 **3–11 步**。以下直接列出模型轉換、產物交接、影像處理與記憶體配置的實作順序。

| 步驟 | 實際工作與工程重點 | 可閱讀的實作 |
| --- | --- | --- |
| 3. YOLO 匯出、量化與 N6 產碼 | **Python／PyTorch（`.pt`）→ ONNX → TensorFlow SavedModel → 逐通道 INT8 量化（TFLite）→ ST Edge AI／Neural-ART → N6 網路與介面（C／H）、權重（BIN）及執行指令**。設定校正影像、逐通道量化及 INT8 輸入輸出，核對模型介面，再完成 N6 參考工程的編譯、連結與封裝 | [完整模型轉換與量化](../vision/deployment/README.md)、[N6 產碼與建置流程](../tools/development-history/vision_03_generate_and_build_vision.sh) |
| 4. 配對推論支援元件 | 將視覺參考工程的神經網路執行函式庫 **12.0.0**、正式底座的 **11.0.0** 統一配對至 **12.0.1**；同步標頭、函式庫與 NPU 支援來源，保留 FreeRTOS 抽象層及非同步等待／完成處理 | [參考工程配對](../tools/development-history/vision_02_match_vision_runtime.py)、[正式工程配對](../tools/development-history/vision_06_match_main_runtime.py)、[ai.mk](../firmware/mks/ai.mk) |
| 5. 移入模型並替換建置項目 | 將六項視覺產物移入 `firmware/Model/`；移除原掌心／手部關鍵點模型的建置項目，更新模型初始化及輸入輸出指標，核對張量數量、形狀、型別與量化參數 | [六項產物移植](../tools/development-history/vision_05_copy_vision_artifacts.sh)、[建置清單修改](../tools/development-history/vision_07_update_model_build_list.py)、[模型資料適配](../tools/development-history/vision_11_adapt_model_data.py) |
| 6. 配置攝影機與模型輸入 | 配置攝影機影像擷取與處理管線（DCMIPP）的顯示及推論路徑；取顯示視野中央正方形，縮放為 **256×256 RGB UINT8**，建立輸入區域與 LCD 顯示區域的幾何對應 | [app_cam.c](../firmware/Src/app_cam.c)、[攝影機與記憶體配置流程](../tools/development-history/vision_13_configure_camera_and_memory.py) |
| 7. 移植實例分割後處理 | 接入 ST 後處理核心及 YOLOv8 轉接層，處理 **1×116×1344** 偵測張量與 **1×64×64×32** 遮罩原型；整合量化資訊、框解碼、非極大值抑制（NMS）與遮罩重建 | [後處理移植](../tools/development-history/vision_08_import_postprocessing.py)、[YOLOv8 轉接層](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c)、[後處理設定](../firmware/Inc/postprocess_conf.h) |
| 8. 建立指定物件搜尋 | 將杯子、瓶子、手機對應至類別 **41、39、67**；選目前目標類別的最高信心框，要求**連續兩幀且框交併比（IoU）至少 0.30**才判定找到；切換目標時清除舊狀態 | [搜尋應用整合](../tools/development-history/vision_12_integrate_vision_application.py)、[app.c](../firmware/Src/app.c) |
| 9. 顯示框、遮罩與狀態 | 將模型座標映射回 LCD 中央辨識區域；分開保存結果遮罩與繪圖遮罩，顯示工作在互斥鎖內複製快照、鎖外繪圖，避免下一輪後處理覆寫顯示資料 | [app.c 的結果與繪圖快照](../firmware/Src/app.c)、[資料交接架構](architecture.md) |
| 10. 修正中斷與影像交接 | 以緩衝佇列及計數號誌交接影像；修正 `bqueue_get_free` 的中斷路徑，使用 `xSemaphoreTakeFromISR` 與 `portYIELD_FROM_ISR`；影像快取處理、複製及模型輸入快取維護完成後，才歸還相機緩衝 | [app.c 的佇列及推論工作](../firmware/Src/app.c)、[中斷與應用整合流程](../tools/development-history/vision_12_integrate_vision_application.py) |
| 11. 配置視覺記憶體與分離映像 | 將應用 SRAM 從 **1,535 KiB 調整為 1,023 KiB**，止於 `0x34100000`；將視覺指令放在 `0x71380000` 的獨立區段、大型緩衝放在外部 PSRAM；分開抽取主應用與視覺指令，避免位址空洞膨脹映像 | [連結腳本](../firmware/Gcc/STM32N657xx.ld)、[Makefile](../firmware/Makefile)、[記憶體配置與映像邊界](memory-deployment.md) |

**模型匯出與量化依據：**[視覺流程](../vision/deployment/README.md)直接連到作者的 PyTorch 匯出 ONNX／SavedModel 成功日誌、逐通道 INT8 設定、量化日誌、電腦端比較程式與 N6 介面檢查，涵蓋 TFLite 進入 N6 產碼之前的模型準備工作。

**六項產物交接：**`network.c`、`network.h`、`network_ecblobs.h`、`stai_network.c`、`stai_network.h`、`network_data.xSPI2.bin`。它們分別涵蓋網路程式、模型介面、視覺執行指令及權重；交接流程先檢查來源完整，再移入正式工程。

**後處理與視覺階段結果：**模型包含 80 類、1,344 個候選位置及 32 張 64×64 遮罩原型；信心門檻 **0.50**、NMS 交併比門檻 **0.40**，最多保留 **10** 個結果。ST 後處理演算法保留原來源，本案完成介面、參數、建置、搜尋狀態與顯示資料流的適配。[視覺版建置流程](../tools/development-history/vision_14_build_main_vision.py)及[板端操作紀錄](evidence/development-history/finder_vision_20261004.log)保存加入 KWS 前的建置與運作結果。

## 音訊、訓練與板端部署的逐步工作

最前面的資料蒐集先使用[獨立收音 main.c](../kws/recording_firmware/FSBL/Src/main.c)：DMA 半滿／全滿回呼把樣本複製至 RAM，略過暖機區塊，主迴圈處理逾時、停止 DMA、CRC32 與串列傳輸。這份來源及上游修改已與主機工具一起保存。

以下對應第 **12–20 步**，由初版資料建立推進至板端模型整合；現場補資料、重新訓練與定版同步另列於後段。

| 階段 | 實際工作與工程重點 | 可閱讀的實作 |
| --- | --- | --- |
| 收音韌體啟動工具 | 找出 IDE 偵錯工具；檢查 ELF/BIN、堆疊與入口向量、錄音版本字串；RAM 載入後設定核心狀態，以 main／MicLine 中斷點核對，再解除偵錯連線 | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| 錄音傳輸 | 串列埠獨占、查詢交握、開始錄音、固定長度讀取、逾時、結尾標記、CRC32、WAV 格式與削波統計 | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| 原始資料蒐集 | 依杯子／瓶子／手機／其他詞語／安靜底噪五類收集；三種命令各 12 段、其他詞語 8 段、安靜 3 段，共 **47 段五秒錄音**，格式為 **16 kHz、16 位元、單聲道**；檢查格式、保存來源與工作階段資訊，支援中斷接續 | [collect_n6.py](../kws/collect_n6.py) |
| 切段與資料分組 | 以短時能量切出發音，補成一秒並避免切入相鄰單字；先按五秒原始錄音分訓練／驗證，再切短片段，初版得到 **142 段訓練及 49 段驗證片段** | [prepare_dataset.py](../kws/prepare_dataset.py) |
| 音訊特徵 | 對 16,000 點音訊去平均值，使用 **480 點週期漢寧窗、320 點位移與 512 點 FFT**；通過 40 個 HTK 梅爾濾波器、對數及正交 DCT，形成 **49×13×1 MFCC 特徵**；以訓練資料計算標準化並保存前處理係數 | [定版 train_kws.py](../kws/training_snapshot/train_kws.py) |
| 客製 KWS 模型 | 建立 49×13×1 輸入的深度可分離卷積網路；五分類、資料增強、類別權重與訓練紀錄 | [網路架構與資料增強](../kws/training_snapshot/train_kws.py) |
| KWS 量化與匯出 | 以代表資料集將 Keras／SavedModel 轉為 INT8 TFLite；保存尺度、零點、特徵係數及浮點／量化結果 | [export_int8](../kws/training_snapshot/train_kws_groupcv.py)、[保留音訊報告](evidence/kws-int8-holdout.json) |
| N6 模型產碼 | 為 KWS 設定專用 RAM／Flash、產碼選項與獨立網路名稱，經工具內部 ONNX 再由 Neural-ART 編譯，與視覺模型共同連結 | [產碼配置](../kws/deployment/README.md)、[原始命令與報告](evidence/development-history/README.md)、[kws.mk](../firmware/mks/kws.mk) |
| 連續收音驅動整合 | 配置 MDF1 腳位、濾波、抽取與 IC8 分頻，保留影像系統共用 PLL2；以 GPDMA 循環鏈結及半滿／全滿回呼收樣，暖機後寫入 **32,768 點環形緩衝**；至少新增 **3,200 點**才取最新 **16,000 點**，名目約 200 毫秒，實際受排程影響 | [finder_mic.c](../firmware/Src/finder_mic.c) |
| CPU／DMA 一致性 | DMA 緩衝與描述節點對齊；快取清理／失效與記憶體屏障；快照複製若被延遲至資料可能覆寫則捨棄 | [cache_prepare／receive_block／finder_mic_take](../firmware/Src/finder_mic.c) |
| C 前處理與模型介面 | 以 CMSIS-DSP 實數 FFT 移植 C MFCC，處理直流與奈奎斯特頻率儲存位置，經標準化、截限及量化產生 **637 個 INT8 特徵**；工作區靜態配置，並核對形狀、型別、尺度與零點 | [finder_kws.c](../firmware/Src/finder_kws.c)、[係數表](../firmware/Inc/finder_kws_tables.h) |
| CPU／NPU 一致性 | CPU 寫新輸入前，先處理 NPU 快取與 CPU 舊副本；寫入後清理 CPU 快取；等待非同步推論完成並重設下一次推論狀態 | [kws_begin_input_update／prepare_input_cache／finder_kws_classify](../firmware/Src/finder_kws.c) |

KWS 的完整路線是 Keras／SavedModel → INT8 TFLite → ST Edge AI 內部 ONNX 與量化中繼資料 → Neural-ART → N6。[原始產碼日誌](evidence/development-history/codegen_20261008/codegen.log)保留內部 ONNX 檔名與實際編譯器呼叫；此 ONNX 是 ST 工具鏈的內部中介表示。資料驗證以原始錄音和 PCM 內容分組，評估範圍為這些來源組別；跨說話者測試尚未執行。

## 即時系統、記憶體與交付工作

第 **17–21 步**完成第二模型、收音、快取與工作的協作；下表的建置與 IDE 項目也對應第 **22、31 步**。定版映像與開機交接在後段另行展開。

| 工作 | 實作內容 | 入口 |
| --- | --- | --- |
| 雙模型排程 | 單一推論工作依序輪詢 KWS 與執行 YOLO，共用 NPU；顯示與 ISP 為另外的工作 | [nn_thread_fct／dp_thread_fct／isp_thread_fct](../firmware/Src/app.c) |
| 攝影機與顯示協作 | DCMIPP 顯示與推論管線、雙輸入緩衝、計數號誌、顯示互斥鎖、遮罩快照及快取維護 | [app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c) |
| 目標與狀態一致性 | 接受語音後切換類別；用目標世代編號捨棄推論途中切換前的舊結果；連續框 IoU 確認後顯示 FOUND | [finder_select_target 與推論結果發布](../firmware/Src/app.c) |
| 開機整合 | 沿用 ST 時脈、NPU、CPU 快取、外部記憶體、UART、顯示與 FreeRTOS 啟動，改接本案模型 | [main.c](../firmware/Src/main.c) |
| 記憶體區隔 | 應用 SRAM、顯示與後處理 PSRAM、獨立視覺指令區；保留 KWS RAM 0x91FC0000／256 KiB、權重 Flash 0x70700000／64 KiB | [連結腳本](../firmware/Gcc/STM32N657xx.ld)、[KWS 記憶體池](../kws/deployment/kws.mpool) |
| 建置整合 | 納入兩模型、HAL MDF、CMSIS-DSP 與執行環境；統一 FFT 相關編譯設定；將 .flash_section 分開輸出 | [Makefile](../firmware/Makefile)、[kws.mk](../firmware/mks/kws.mk)、[ai.mk](../firmware/mks/ai.mk) |
| IDE 整理 | 同步來源與標頭的瀏覽入口，核對既有連結、備份、競態檢查與原子替換；建置入口支援 GCC_PATH 並核對 GCC 14.3.1 | [原始同步工具](../tools/ide/README.md)、[IDE 專案](../firmware/STM32CubeIDE/STM32N6570-DK/.project)、[IDE 建置入口](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) |
| 定版與交付 | 保存來源版本、模型與工具設定、訓練快照、五映像的本機定版包及既有寫入驗證紀錄 | [來源紀錄](source-provenance.json)、[結果](results.md)、[建置說明](build.md) |

KWS 產碼沒有啟用 epoch controller（執行階段控制器）；CPU 執行模型控制流程，NPU 仍執行對應硬體運算。控制程式連入主應用，另配置語音權重；沒有獨立 KWS ecblob 映像。本版由同一推論工作依序執行兩個模型，控制流程與權重各自按配置連結。

[定版編譯報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)記錄 11 個硬體及 1 個軟體 Softmax 執行階段，權重配置 11,409 位元組、活化值 17,440 位元組。這些是 KWS 編譯統計，與兩個模型整合後的全系統記憶體峰值分開解讀。

本機交付包將雙模型系統分為五份映像：FSBL、應用、視覺權重、KWS 權重及視覺執行指令。映像封裝採無金鑰模式（-nk），產生啟動所需的封裝標頭，未使用密碼學簽章。

## 封裝除錯、數值比對與現場診斷

對應第 **22–25 步**：先確認映像能正確啟動，再從固定輸入到即時音訊逐層比較，最後分辨資料／模型問題與命令接受條件。

| 階段 | 實際工作與工程重點 | 可閱讀的實作 |
| --- | --- | --- |
| 啟動與封裝診斷 | 排查寫入驗證成功卻無畫面、無串列輸出的版本；比較 ELF、原始二進位與封裝有效載荷，確認內容一致後將偏移 **`0x240 → 0x400`**，重新封裝、核對內容與對齊，再接續部署 | [有效載荷檢查](../tools/development-history/inspect_boot_payload.py)、[對齊流程](../tools/development-history/realign_and_flash_application.sh)、[後續寫入](../tools/development-history/retry_aligned_application_flash.sh) |
| 分層比對與除錯 | 固定 INT8 輸入直接測模型，再由同一 PCM 測完整 C 前處理；比較輸入差異與輸出量化值 | [finder_kws_compare](../firmware/Src/finder_kws.c)、[比對設定](../firmware/Inc/finder_kws_compare.h) |
| 即時原始資料回傳 | 保存同一視窗的 PCM、637 個 INT8 特徵與五個輸出，以分段十六進位及 CRC32 回傳供電腦比對 | [finder_kws_live_capture／live_send](../firmware/Src/finder_kws.c) |
| 現場誤判與漏接定位 | 同一安靜視窗在板端與電腦重算皆判成手機；瓶子雖排名第一，分數仍未達接受門檻。對照相同視窗的峰值、特徵、五類分數、第一／第二名分差與削波統計，區分資料／模型表現和前處理、部署問題 | [即時比較報告](evidence/development-history/live_comparison_20261007.json)、[診斷記錄流程](../tools/development-history/record_voice_diagnostics.py) |
| 語音接受狀態機 | 音訊峰值至少 **2,500**、最高分至少 **90%**、領先次高分至少 **25 個百分點**；連續兩個視窗命中，命令間隔至少 **1,200 毫秒**；接受後等兩個安靜視窗才重新啟用，畫面保留最後接受的命令 | [finder_voice_poll](../firmware/Src/app.c) |

## 現場資料迭代與定版同步

對應第 **26–28 步**。先補四段現場音訊後，離線結果仍不足以解決現場漏接，因此繼續收集 **48 段**板端音訊：**32 段**加入開發、**16 段**保留評估。原 142 段訓練、49 段驗證、先前四段與新增 32 段合成 **227 段開發資料**；原 49 段不再作為獨立保留集。

| 階段 | 實際工作與工程重點 | 可閱讀的實作 |
| --- | --- | --- |
| 現場資料迭代 | 保存即時資料重訓版本；按發音能量選取板上視窗、加入實際底噪與現場語音，與保留資料分開 | [live v3 訓練程式](../kws/train_kws_live_v3.py)、[收集計畫](../kws/live_collection_plan.json)、[板端擷取](../firmware/Src/finder_kws.c) |
| 防止資料洩漏 | 依原始錄音分組；PCM 雜湊識別相同音訊並合併組別；拒絕開發與保留測試重複；每折的標準化及背景噪音僅取訓練組 | [load_development／make_splits／make_training](../kws/training_snapshot/train_kws_groupcv.py) |
| 分組交叉驗證 | 完成分層分組五折驗證，INT8 合計 **224/227（98.68%）**；五折最佳輪數 **82、28、66、9、79**，取中位數 **66 輪**，使用全部 227 段重新訓練；16 段保留音訊的浮點與 INT8 結果皆為 **15/16（93.75%）** | [定版分組訓練](../kws/training_snapshot/train_kws_groupcv.py)、[五折報告](evidence/kws-groupcv.json) |
| 同步定版模型與前處理 | 重新產碼後一起更新模型程式、權重、特徵係數、量化尺度及零點，輸入零點由 **8 改為 7**；關閉開發用收集與比較模式，再建置正式韌體，保存模型雜湊與設定 | [定版產碼](../tools/development-history/generate_groupcv_model.py)、[安裝與建置](../tools/development-history/install_build_groupcv.py)、[板端係數](../firmware/Inc/finder_kws_tables.h) |
| 核對正式產碼輸出 | 原產物檢查將工具工作目錄的同名檔一起算入而停止；後續限定正式輸出目錄，重新確認產物後完成安裝與建置 | [產碼輸出核對](../tools/development-history/inspect_groupcv_codegen.py)、[KWS 部署設定](../kws/deployment/README.md) |

[訓練歷程](../kws/training_history/README.md)另外補入初版訓練原檔，呈現早期資料增強、現場補樣本、發音邊界限制，到分組定版的實作演進。[48 段現場收集清單](evidence/development-history/live_dataset_manifest_20261008.json)保存 32 段訓練、16 段保留及逐段 PCM 雜湊。

## 五份映像、開機交接與定版部署

對應第 **29–32 步**。將模型產碼的配置、韌體連結位址與 Flash 寫入位置逐項對照，保存映像長度與雜湊，再部署定版更新。

| 映像 | 儲存位置 | 執行時用途 |
| --- | --- | --- |
| 第一階段開機載入程式（FSBL） | 依 `ai_fsbl.hex` 內含位址 | 準備載入環境並將主應用載入 SRAM |
| 主應用 `finder_signed.bin` | Flash `0x70100000` 起 | 主應用連結在內部 SRAM `0x34000400` 起執行，包含 FreeRTOS、周邊、模型控制與應用邏輯 |
| 視覺權重 `vision_weights.bin` | Flash `0x70380000` 起 | YOLO 模型權重 |
| 語音權重 `kws_weights.bin` | Flash `0x70700000` 起，保留 64 KiB | KWS 模型權重 |
| 視覺執行指令 `vision_commands.bin` | Flash `0x71380000` 起，保留 2 MiB | 視覺執行階段控制器指令 |

**開機交接：**晶片內建開機程式（Boot ROM）載入 FSBL，再由 FSBL 將主應用從 Flash 載入 SRAM 並交出控制權；應用啟動碼進入 `main()`，先啟動 FreeRTOS 排程器，再由初始化工作完成時脈、NPU、外部記憶體及周邊設定，建立推論、顯示與 ISP 工作。[主應用初始化](../firmware/Src/main.c)與[工作建立](../firmware/Src/app.c)保存實際順序。

**邊界與更新範圍：**核對視覺權重的實際內容終點與 KWS 起點，不能將上游視覺模型池的全部容量直接視為雙模型工程可用範圍。定版更新直接寫入並驗證**主應用及 KWS 權重**，其餘三份映像沿用既有配置。[定版寫入流程](../tools/development-history/flash_groupcv.py)、[映像清單](evidence/development-history/deployment_20261008/flash_manifest.json)、[驗證摘要](evidence/development-history/deployment_20261008/flash_verified.json)及[完整記憶體配置](memory-deployment.md)提供對照。

**工程保存與展示：**完成 IDE 來源入口、可指定編譯器的建置路徑、程式與設定保存、中英文文件及 GitHub 公開；[實機展示影片](https://youtu.be/m7wET9g5u6k)已放入首頁。獨立供電與斷電重上仍依現有紀錄標示為尚未核對完成。

## 驗證與版本對應

| 階段 | 保存的結果 | 適用範圍 |
| --- | --- | --- |
| 視覺主工程 | 加入 KWS 前的板端紀錄包含杯子與手機的 FOUND 結果 | [視覺版操作紀錄](evidence/development-history/finder_vision_20261004.log)；與定版語音接受紀錄分開 |
| 固定五類數值比較 | 五類各一個樣本，固定特徵（INPUT）與原始音訊（PCM）兩路分類均與電腦一致；PCM 路徑每段 637 個 INT8 特徵逐項一致，輸出最大差異不超過 1 個量化整數單位 | [固定參考資料](evidence/development-history/fixed_reference_20261007.json)與[原始比對結果](original-history-review.md)；屬早期比較版本 |
| 前處理與部署比較 | 即時四例 INT8 特徵與電腦完全一致，輸出最大整數差異為 0、0、3、1 | [早期比較模型的原始報告](evidence/development-history/live_comparison_20261007.json)；固定 INPUT／PCM 比較程式另保留在韌體中 |
| 模型與資料問題定位 | 同一 silence 樣本在板端、電腦特徵輸入及完整 PCM 前處理三路皆判成 phone | 同份比較報告；保留失敗案例，與後續現場資料改進分開記錄 |
| 分組定版 | 五折開發驗證 224/227（98.68%）；保留音訊 INT8 15/16（93.75%） | [評估報告](evidence/README.md)；五折用於開發與選輪，保留結果是 16 段單窗離線評估 |
| 定版板上操作 | cup、bottle、phone 各兩次接受；同輪保存的視覺訊息皆為 found=0 | [定版板端操作日誌](evidence/development-history/voice_groupcv_20261008.log)；統計語音接受，與較早視覺 FOUND 紀錄分開 |
| 部署 | 應用與 KWS 權重的寫入及驗證成功 | [部署清單與紀錄](evidence/development-history/deployment_20261008/)；其餘映像沿用已配置內容 |

完整[結果說明](results.md)依各次模型雜湊與日誌區分版本。[實機展示影片](https://youtu.be/m7wET9g5u6k)已提供；雙模型系統的獨立供電與冷啟動不列為已實測通過。

本庫保存資料蒐集韌體與主機工具、訓練歷程、比對與即時擷取程式、模型配置、整合應用及[原始證據](evidence/development-history/README.md)。HAL、BSP、CMSIS-DSP、FreeRTOS、ST 推論執行期與視覺後處理保留上游來源。模型權重、原始音訊、模型產碼與預建映像的公開範圍及建置依賴見[第三方來源說明](../THIRD_PARTY_NOTICES.md)與[建置文件](build.md)。
