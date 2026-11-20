# 雙模型系統實作與證據索引

[繁體中文](development-coverage.md) | [English](development-coverage.en.md)

本索引對照從平台與收音工具、視覺模型產碼、語音資料與 KWS 訓練，到兩模型數值移植、系統整合、燒錄與定版的工作。各階段列出實際程式、配置與結果；部分工作交錯進行，章節編號不是每一步的時間順序。完整流程見[工程流程](engineering-workflow.md)，早期失敗、修正與執行結果見[原始開發歷程覆核](original-history-review.md)。

## 0. 系統目標、平台與模型介面

| 工作 | 實作內容 | 程式與設定 |
| --- | --- | --- |
| 系統行為 | 語音 cup／bottle／phone 或 USER1 選擇目標；視覺持續執行，LCD 顯示搜尋狀態、框與遮罩 | [app.c](../firmware/Src/app.c)、[架構](architecture.md) |
| 工具與執行期 | GCC 14.3.1、ST Edge AI 4.0.1、Neural-ART 1.1.3-275、HAL 1.3.0、FreeRTOS 10.6.2；配置模型、MDF 與 CMSIS-DSP 建置相依 | [建置說明](build.md)、[ai.mk](../firmware/mks/ai.mk)、[kws.mk](../firmware/mks/kws.mk) |
| 應用框架 | 沿用 ST 雙模型 FreeRTOS 與相機框架，改接 KWS／YOLO、目標狀態與顯示資料 | [來源紀錄](source-provenance.json)、[app.c](../firmware/Src/app.c) |
| 視覺模型來源 | 選用來源與 SHA-256 已固定的 ST 量化實例分割模型，整合其 N6 產碼與執行期介面 | [sources.txt](../sources.txt)、[模型介面](engineering-workflow.md) |
| 視覺產碼與執行期對齊 | 在本專案執行 ST Edge AI 4.0.1 視覺產碼與參考建置；將六份產碼檔移入正式韌體，統一標頭、函式庫與 NPU 支援至 Runtime 1201 | [視覺部署流程](engineering-workflow.md)、[原始歷程](original-history-review.md) |
| 視覺輸入與輸出 | 256×256 RGB UINT8 輸入、兩組 INT8 輸出；檢查形狀、型別、指標及大小，對接偵測與遮罩原型 | [app.c](../firmware/Src/app.c)、[ST 後處理轉接層](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c) |
| 後處理與物件選擇 | 接入 ST 解碼、非極大值抑制（NMS）與遮罩生成，篩選三種目標類別，加入連續幀確認與畫面映射 | [app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c) |

## 1. 音訊資料從板子到訓練集

| 工作 | 實作內容 | 程式與證據入口 |
| --- | --- | --- |
| 獨立收音韌體 | 從官方播放範例改為五秒 RAM 錄音；DMA 半滿／全滿複製、暖機、逾時、錯誤、長度與 CRC32 | [錄音 FSBL 與上游差異](../kws/recording_firmware/README.md) |
| RAM 啟動與偵錯 | ELF／BIN、堆疊與入口向量檢查、版本字串、載入、核心狀態、中斷點及解除偵錯連線 | [主機工具](../kws/recording_tools/README.md) |
| 收音建置與啟動排錯 | 補齊 UART／UART_EX 建置連結，從 14 個錯誤修到 0 個錯誤；區分 RAM 寫入驗證與實際啟動，以 GDB 中斷點、交握、CRC32 及 WAV 回放逐層確認 | [原始歷程](original-history-review.md)、[錄音來源差異](../kws/recording_firmware/README.md) |
| 錄音協定與接收 | 串列獨占、查詢／開始交握、固定長度、結尾、逾時與 CRC32；WAV 格式及削波統計 | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| 分類資料收集 | cup／bottle／phone／unknown／silence 計畫、來源與工作階段、格式核對及中止後接續 | [collect_n6.py](../kws/collect_n6.py) |
| 切段與分組 | 短時能量定位發音、一秒片段與補零、相鄰發音邊界；先依原始錄音分組再切片 | [prepare_dataset.py](../kws/prepare_dataset.py) |
| 連續收音移植 | MDF／GPDMA 循環鏈結、時脈與存取屬性、DMA 快取、環形緩衝及滑動視窗 | [finder_mic.c](../firmware/Src/finder_mic.c) |
| 原始即時視窗回傳 | 同一 PCM、INT8 特徵與模型輸出封包、分段十六進位及 CRC32，供分層比對 | [finder_kws.c](../firmware/Src/finder_kws.c) |
| 現場資料迭代 | 收集清單、標籤、訓練／保留用途、逐段 PCM 雜湊 | [48 段資料清單](evidence/development-history/live_dataset_manifest_20261008.json) |

## 2. KWS 從特徵到 NPU

| 工作 | 實作內容 | 程式與證據入口 |
| --- | --- | --- |
| Python 特徵前處理 | 去平均值、Hann 窗、FFT、HTK Mel、對數、DCT、標準化與係數保存 | [定版訓練](../kws/training_snapshot/train_kws.py) |
| 客製五分類網路 | 49×13×1 輸入、深度可分離卷積、資料增強、類別權重、訓練紀錄 | 同上、[初版及迭代歷程](../kws/training_history/README.md) |
| 現場誤判修正流程 | 比對早期安靜誤判、加入現場語音／底噪、調整增強的發音邊界與重訓版本 | [歷程](../kws/training_history/README.md)、[即時比較](evidence/development-history/live_comparison_20261007.json) |
| 資料洩漏防護 | 原始錄音分組、相同 PCM 合併來源組別並拒絕標籤矛盾、拒絕開發／保留重複，每折標準化與背景噪音只用訓練組 | [分組訓練](../kws/training_snapshot/train_kws_groupcv.py) |
| 五折與最終訓練 | 分層分組五折、選擇輪數、定版訓練；保留音訊另評估 | [五折與保留報告](evidence/README.md) |
| INT8 匯出 | 代表資料集、尺度／零點、模型與前處理係數、浮點／量化結果 | `export_int8`、[訓練快照](../kws/training_snapshot/README.md) |
| N6 產碼 | 專用網路名稱與記憶體池；TFLite → ST 內部 ONNX／量化資訊 → Neural-ART | [配置](../kws/deployment/README.md)、[原始編譯紀錄](evidence/development-history/README.md) |
| C 前處理與介面 | CMSIS-DSP 浮點 FFT、Mel／DCT、標準化後 INT8 量化；形狀／型別及尺度／零點核對 | [finder_kws.c](../firmware/Src/finder_kws.c)、[係數表](../firmware/Inc/finder_kws_tables.h) |
| CPU／NPU 一致性 | 寫入前處理舊快取，寫入後清理，等待非同步推論完成並重設下一次狀態 | 同上；KWS 並非全程定點前處理 |
| 分層對照 | 固定 INT8 INPUT 測模型、同 PCM 測 C 前處理，再比較即時視窗三路結果 | [比較程式](../firmware/Src/finder_kws.c)、[結果與原始證據界線](results.md) |

五折結果是開發與選輪資料；保留測試是 16 段單窗資料。原始錄音分組不等於做過跨說話者驗證。早期比較模型與最後分組模型保留各自雜湊，不能混算結果。

## 3. 雙模型系統整合

| 工作 | 實作內容 | 程式與證據入口 |
| --- | --- | --- |
| 框架移植 | 以 ST 手部雙模型 FreeRTOS 框架為基礎，改接 YOLO 與 KWS | [來源紀錄](source-provenance.json)、[app.c](../firmware/Src/app.c) |
| 模型共用 NPU | 在同一推論工作依序輪詢 KWS 與執行 YOLO，顯示及 ISP 由其他工作協作 | `nn_thread_fct`／`dp_thread_fct`／`isp_thread_fct` |
| 相機輸入適配 | 把上游手部模型的寬高比處理改為中央正方形區域，再縮放到模型輸入 | [app_cam.c](../firmware/Src/app_cam.c) |
| 相機中斷佇列適配 | 沿用上游佇列，修正中斷情境的號誌取得及必要的工作切換，使用 `xSemaphoreTakeFromISR` 與 `portYIELD_FROM_ISR` | [相機輸入佇列](../firmware/Src/app.c)、[原始歷程](original-history-review.md) |
| 目標選擇與語音接受 | 三種物件、音量／分數／分差、連續視窗、命令間隔、安靜後重啟用、USER1 操作 | `finder_voice_poll`、`finder_select_target` |
| 跨工作一致性 | 目標世代防止切換後發布舊結果、框的連續幀 IoU、遮罩快照與顯示互斥 | [app.c](../firmware/Src/app.c) |
| 記憶體與建置 | 應用 SRAM、顯示／後處理 PSRAM、視覺指令區、KWS 專用 RAM／Flash；MDF、DSP、兩模型共同連結 | [連結腳本](../firmware/Gcc/STM32N657xx.ld)、[建置清單](../firmware/mks/kws.mk) |
| 診斷與降級行為 | 啟動／推論錯誤、語音與搜尋狀態、收音統計、手動切換路徑 | [app.c](../firmware/Src/app.c)、[finder_mic.c](../firmware/Src/finder_mic.c) |

視覺持續執行，語音改變搜尋目標。三工作能交錯執行，不代表兩模型同時占用 NPU。底層時脈、AXISRAM、GPU2D、RIF、UART 與 FreeRTOS 啟動主要沿用上游；本作品的價值包含選用、適配與整合，不能把整份框架描述為自行重寫。

### 資料所有權、數值與故障處理細節

以下說明緩衝、周邊、特徵及狀態交接的實作方式。語音錯誤隔離描述執行期間的程式路徑；不涵蓋初始化斷言失敗或另行故障注入驗證。

| 細節 | 原始碼顯示的處理及用途 | 程式入口 |
| --- | --- | --- |
| 共享時脈 | 保留既有 PLL2，僅設定 IC8 分頻為 61 並檢查 MDF 時脈，將收音接入已運作的系統 | [finder_mic_start](../firmware/Src/finder_mic.c) |
| 周邊存取與 DMA | PE2／PE8 腳位、MDF 安全／特權與 DMA 權限；來源為 DFLTDR 高 16 位元，描述節點／緩衝分別 64／32 位元組對齊 | 同上 |
| 音訊快照所有權 | 回呼處理快取及屏障後發布環形位置；一秒快照處理跨界，若複製被延遲至可能覆寫就放棄該次資料 | `receive_block`、`finder_mic_take` |
| RAM 啟動診斷 | 檢查向量與入口、Boot ROM 狀態，設定核心暫存器；main／MicLine 與錯誤中斷點保留失敗診斷，結束清理偵錯程序 | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| Linux 接收可靠性 | 檔案鎖與串列獨占、非阻塞讀取、單調時鐘期限、完整性核對、端序及離開時恢復設定 | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| 特徵數值格式 | 正確處理實數 FFT 的直流與奈奎斯特儲存位置；浮點 Mel／對數／DCT 後才量化 | [encode_mfcc](../firmware/Src/finder_kws.c) |
| 訓練組別完整性 | 相同 PCM 合併組別，而不是刪除全部重複資料列；檢查五類覆蓋、組別不交疊及每筆資料恰好驗證一次 | [make_splits 等](../kws/training_snapshot/train_kws_groupcv.py) |
| 相機與模型緩衝 | 相機緩衝快取失效後，先複製到模型輸入並清理快取，再歸還相機緩衝，分開下一幀擷取與模型輸入的生命週期 | [nn_thread_fct](../firmware/Src/app.c) |
| 模型／顯示遮罩隔離 | 後處理遮罩先複製成結果快照，顯示工作在鎖內再取繪圖快照，之後於鎖外畫圖 | `nn_thread_fct`、`dp_thread_fct` |
| 裁切與畫面座標 | 同一顯示視野內取中央方形，框與遮罩映射回 LCD 方形區域，處理遮罩邊界與透明疊圖 | [app_cam.c](../firmware/Src/app_cam.c)、[Display_NetworkOutput](../firmware/Src/app.c) |
| 語音錯誤隔離 | 運行中的收音／分類回傳錯誤時停用語音並顯示錯誤，視覺工作與按鍵操作仍有繼續執行的路徑；不宣稱自動復原，也不涵蓋初始化斷言失敗 | `finder_voice_poll`、`nn_thread_fct`、`dp_thread_fct` |
| 手動備援與去彈跳 | USER1 上升緣與 200 ms 間隔，與語音共用目標選擇介面 | `dp_thread_fct`、`finder_select_target` |
| DSP 編譯一致性 | FFT 物件與前處理物件採相同編譯設定，配合此版 CMSIS-DSP 路徑 | [kws.mk](../firmware/mks/kws.mk) |

來源分工：`main.c` 的修改集中於模型標頭與啟動資訊；`FreeRTOSConfig.h` 與 ST 基底相同。三工作、靜態配置與相機佇列以 ST 框架為基礎；本案另外修正佇列的中斷情境號誌操作，並加入音訊／視覺模型及新的資料、狀態交接。底層來源與實際修改分開歸屬。

## 4. 定版、IDE 與交付

| 工作 | 保存內容 | 程式與證據入口 |
| --- | --- | --- |
| 五映像分工 | FSBL、應用、視覺權重、KWS 權重、視覺指令；記錄位址及雜湊，分開抽取 ELF 區段 | [工程流程](engineering-workflow.md)、[來源與證據](evidence/development-history/README.md)。五映像不是五個模型 |
| 既有建置與寫入 | 定版建置報告、應用與 KWS 權重寫入及驗證紀錄 | [部署紀錄](evidence/development-history/deployment_20261008/) |
| 來源與版本封存 | 原本 firmware／vision 來源、模型版本、訓練快照、本機整合 Git、定版包與雜湊 | [來源紀錄](source-provenance.json)、[訓練快照](../kws/training_snapshot/README.md)；公開庫與本機完整封存的範圍不同 |
| IDE 來源同步 | linked resources、路徑核對、預覽、備份、雜湊競態檢查、原子替換、編譯器入口 | [同步工具](../tools/ide/README.md)、[建置說明](build.md) |
| 公開整理 | 來源聲明、程式導覽、證據索引、模型／映像公開界線、提交與同步 | [材料盤點](publication-review.md)、[第三方說明](../THIRD_PARTY_NOTICES.md) |
| 展示影片 | 預定補拍整合系統的實際操作 | 待補；不以其他版本的測試代替 |

獨立錄音範例的 FSBL 原始碼與整合系統採用的官方預建啟動 FSBL 是不同材料；公開前者不代表後者已具完整建置來源。映像的無金鑰標頭封裝不描述為密碼學簽章。

## 5. 結果與版本對應

| 結果 | 對應資料 | 解讀 |
| --- | --- | --- |
| 早期四例即時比較 | [live_comparison_20261007.json](evidence/development-history/live_comparison_20261007.json) | INT8 特徵差異皆為 0；輸出最大整數差異為 0、0、3、1，屬於數值移植比較 |
| 固定 INPUT／PCM 路徑 | [比較程式](../firmware/Src/finder_kws.c)、[電腦參考](evidence/development-history/fixed_reference_20261007.json)、[原始對話中的實際輸出](original-history-review.md) | 五類在兩路各 5/5 正確；PCM 路徑每例 637 個 INT8 特徵完全一致，輸出最大整數差異為 0，silence 為 1。這是五個固定案例的數值一致性檢查 |
| 分組模型五折驗證 | [kws-groupcv.json](evidence/kws-groupcv.json) | 224/227，98.68%，用於開發與選輪 |
| 定版 INT8 保留音訊 | [kws-int8-holdout.json](evidence/kws-int8-holdout.json) | 15/16，93.75%，16 段單窗離線評估 |
| 定版板上語音接受 | [2026-10-08 操作日誌](evidence/development-history/voice_groupcv_20261008.log) | 三個指定命令各接受兩次；同輪視覺皆為 found=0，不能把語音接受次數當成完整找物成功次數 |
| 本案較早視覺整合版本 | [2026-10-04 視覺日誌](evidence/development-history/finder_vision_20261004.log) | CUP、PHONE 有 FOUND 紀錄，與定版語音紀錄分屬不同版本 |
| 應用與 KWS 權重部署 | [flash_verified.json](evidence/development-history/deployment_20261008/flash_verified.json) | 保存兩份映像的成功寫入驗證；封存複本雜湊核對與板上 Flash 驗證分開解讀 |

模型版本、數值與操作結果的完整說明見[結果頁](results.md)。本案的獨立供電與冷啟動未列為實測通過。公開儲存庫提供應用、訓練、工具、配置與證據；模型權重、原始音訊、模型產碼及預建映像依[公開範圍](../THIRD_PARTY_NOTICES.md)處理，重建須具備[相依項目](build.md)。
