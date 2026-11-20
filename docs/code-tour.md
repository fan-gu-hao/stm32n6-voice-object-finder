# 程式導讀與實作重點

[繁體中文](code-tour.md) | [English](code-tour.en.md)

記憶體配置與燒錄位置的完整對照見[雙模型記憶體與部署](memory-deployment.md)；官方範例版本、實際建置指令及封裝修正見[工具鏈相容性](toolchain-compatibility.md)。

這份導讀依雙模型找物系統的建立順序，涵蓋收音工具、資料與訓練、板端前處理、兩模型整合、記憶體配置及部署。整體步驟見[工程流程](engineering-workflow.md)。

## 1. 從錄音到可訓練資料

| 程式／函式 | 閱讀重點 |
| --- | --- |
| [獨立錄音 main.c](../kws/recording_firmware/FSBL/Src/main.c)：MicRecord／MicCopy／MicCrc32 | 五秒 RAM 錄音、暖機、DMA 半滿／全滿回呼、12 秒逾時、錯誤狀態、長度與 CRC32；中斷只複製、主迴圈傳送 |
| [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) | ELF/BIN 與向量表檢查；RAM 載入；MSP、PC、xPSR、遮罩暫存器設定；main／MicLine 檢查點；偵錯連線清理 |
| [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py)：capture／save | 串列埠獨占、交握重試、帶期限的讀取、音訊標頭、精確位元組數、結尾與 CRC32；WAV 格式、削波統計 |
| [collect_n6.py](../kws/collect_n6.py) | 五類錄音計畫、已完成資料接續、格式與來源資訊 |
| [prepare_dataset.py](../kws/prepare_dataset.py)：speech_regions／extract_word | 短時能量、發音間隔、鄰近單字界線與補零；按原始錄音分組後再切成一秒片段 |

這組主機工具用於建立本專案的語音資料，須搭配對應的獨立收音韌體，說明見[工具文件](../kws/recording_tools/README.md)。其 RAM 載入流程不等同於雙模型應用從外部 Flash 啟動的流程。

獨立收音的 [FSBL 來源、IDE 快照與上游差異](../kws/recording_firmware/README.md)已保存，供對照後續連續收音驅動的演進。

## 2. 特徵、訓練、量化與資料隔離

以[定版 train_kws.py](../kws/training_snapshot/train_kws.py)的 features、augment、build_model 為起點：

- 週期 Hann 窗、HTK Mel 刻度、自然對數及正交 DCT，形成 49×13 特徵。
- 音量變化、限制範圍的時間平移、背景噪音與訊噪比增強，保留發音內容。
- 深度可分離卷積、批次正規化、全域平均池化與五分類輸出。

接著讀[定版 train_kws_groupcv.py](../kws/training_snapshot/train_kws_groupcv.py)：

| 函式 | 工程重點 |
| --- | --- |
| load_development | 按原始錄音建立組別；以 PCM SHA-256 排除保留測試重複；相同 PCM 合併組別並檢查標籤衝突 |
| make_splits | 分層分組五折切分；每折五類覆蓋、組別不交疊、每筆資料恰好驗證一次 |
| make_training | 僅用該折訓練資料計算標準化參數、選背景噪音與做增強；使用類別權重 |
| fit_model | 保存訓練歷程、模型與選輪結果 |
| export_int8 | 代表資料校正、INT8 TFLite 匯出、特徵係數、量化尺度與零點 |
| main／metrics | 匯總五折、選定最終訓練輪數、訓練最終模型並評估另保留的音訊 |

[train_kws_live_v3.py](../kws/train_kws_live_v3.py)保存現場資料迭代版本；[快照說明](../kws/training_snapshot/README.md)標明定版程式來源。歷史腳本保留當時環境相依，不是任意目錄的即裝即用套件。

[訓練歷程](../kws/training_history/README.md)補入最早的訓練原檔，列出從固定平移與背景增強，到發音邊界限制、現場樣本與分組驗證的程式差異。

## 3. 收音驅動、DMA 與環形緩衝

[finder_mic.c](../firmware/Src/finder_mic.c)的 finder_mic_start 保留系統既有 PLL2，設定 IC8 分頻及核對 MDF1 時脈；再配置 PE2／PE8、周邊與 DMA 存取屬性、數位濾波與抽取，以及 GPDMA1 Channel6 的循環鏈結。DMA 描述節點與樣本緩衝分別對齊 64／32 位元組。

HAL_MDF_AcqHalfCpltCallback／HAL_MDF_AcqCpltCallback 每次處理 256 點。receive_block 先處理 DMA 與 CPU 快取一致性，略過 16 個暖機區塊，再寫入 32,768 點環形緩衝，經記憶體屏障後發布寫入位置。

finder_mic_take 取得最新 16,000 點快照，以累積至少 3,200 個新樣本作為取窗門檻；實際間隔受 DMA 區塊與推論工作排程影響。遇到環形跨界分兩段複製；若複製期間被延遲到資料可能遭覆寫則放棄該次快照。錯誤回呼與中斷入口也保留在同一檔案。

## 4. C 前處理、NPU 介面與比對工具

[finder_kws.c](../firmware/Src/finder_kws.c)同時包含正式推論與開發比對。frame、spectrum、power、log_mel 採靜態緩衝，避免放入工作堆疊；這些共享工作區限單一推論工作使用。

| 函式／區段 | 閱讀重點 |
| --- | --- |
| 靜態斷言與 finder_kws_init | 核對輸入輸出數量、形狀、INT8 型別及訓練／產碼量化參數 |
| encode_mfcc | 去直流、480 點窗／320 點位移、512 點實數 FFT；分開處理直流／奈奎斯特頻率儲存位置，計算功率頻譜、40 個 Mel 濾波器、13 維 DCT，再標準化、截限與量化 |
| kws_begin_input_update | CPU 寫新輸入前先清理 NPU 的 64 位元組快取列，再讓 CPU 舊副本失效並執行屏障 |
| prepare_input_cache | 寫入後按 CPU 快取列對齊清理，供 NPU 讀取 |
| finder_kws_classify | 非同步執行狀態與等待事件，區分 MFCC／模型時間；本模型最後為 CPU Softmax，直接讀取 CPU 產生的量化輸出並準備下一次推論 |
| finder_kws_compare | 先以參考 INT8 特徵直接測推論，再用參考 PCM 測前處理＋推論；輸出 input_diff、input_max、output_max 與 CMP_Q |
| finder_kws_live_capture／live_send | 依音訊能量選窗，將 PCM、實際 INT8 特徵與輸出成套回傳，附偏移與 CRC32 |

[比對開關](../firmware/Inc/finder_kws_compare.h)在定版中關閉；程式保留供理解當時的部署驗證方法。前處理係數與參考資料分別見 [finder_kws_tables.h](../firmware/Inc/finder_kws_tables.h)及 [finder_kws_compare_data.h](../firmware/Inc/finder_kws_compare_data.h)。

## 5. 雙模型、即時工作與狀態一致性

[app.c](../firmware/Src/app.c)在 nn_thread_fct 啟動時呼叫一次 stai_runtime_init，再初始化視覺 network_ctx，透過 finder_kws_init 初始化語音專用 context。兩個模型有各自的產碼名稱、上下文及輸入輸出指標，連結至同一套執行環境；推論工作依序輪詢 KWS 與執行 YOLO，不讓兩模型同時使用 NPU。非同步模型呼叫遇到等待狀態時使用 LL_ATON_OSAL_WFE，完成後重設下一次推論狀態。

nn_thread_fct、dp_thread_fct、isp_thread_fct 分別處理推論、顯示及 ISP 更新，沿用官方框架的靜態工作與優先級。[相機輸入佇列](../firmware/Src/app.c)另修正中斷情境的號誌取得與工作切換，使用 `xSemaphoreTakeFromISR`、`portYIELD_FROM_ISR`；這部分包含本案修改。視覺持續執行；語音改變搜尋目標。

| 函式／資料 | 本專案的整合重點 |
| --- | --- |
| nn_thread_fct／nn_input_queue | 相機緩衝透過計數號誌交接；先失效快取、複製至模型輸入並清理快取，再歸還相機緩衝 |
| finder_voice_poll | 峰值至少 2500、分數至少 0.90、領先次高分至少 0.25、連續兩窗、最短間隔 1200 ms；接受後等待兩個安靜視窗重新啟用 |
| finder_select_target／generation | 切換目標時更新世代並清除找到狀態；推論完成時核對世代，捨棄舊目標結果並重新累積連續命中 |
| box_iou／FINDER_CONFIRM_FRAMES | 從指定類別挑最高信心結果，連續兩幀且框交併比至少 0.30，才判定找到（FOUND） |
| result_mask／drawing_mask | 模型輸出先複製為結果快照；顯示工作於互斥鎖內再複製繪圖快照，於鎖外繪製，避免下一輪後處理覆寫 |
| DCMIPP_PipeInitNn／Display_NetworkOutput | 從 LCD 顯示視野取中央正方形輸入，將框與遮罩映回同一方形區域；以官方 NMS／遮罩重建結果完成透明疊圖 |
| dp_thread_fct | USER1 上升緣與 200 ms 間隔去彈跳，與語音共用目標選擇介面；繪圖後清理快取並交換前景緩衝 |
| finder_voice_poll 的 voice_error 路徑 | 執行期間收音／分類回傳錯誤時停用語音並顯示錯誤，程式保留視覺與按鍵繼續執行的路徑；不涵蓋初始化斷言失敗，也不保證共享硬體故障後仍能運作 |

上述錯誤處理是原始碼行為，沒有對應的故障注入驗證或自動復原宣稱。

## 6. 啟動、記憶體、產碼與建置

- [main.c](../firmware/Src/main.c)：沿用官方時脈、NPU／AXISRAM、CPU 快取、外部記憶體、GPU2D、存取屬性、UART 與作業系統初始化；接上本版視覺模型標頭與資訊。
- [app_cam.c](../firmware/Src/app_cam.c)：攝影機管線及模型輸入介面。
- [連結腳本](../firmware/Gcc/STM32N657xx.ld)：應用 SRAM、視覺命令 Flash、顯示／後處理 PSRAM，並保留 KWS 專用 RAM。
- [KWS 產碼設定](../kws/deployment/README.md)：獨立模型名稱、RAM／Flash 位址及 Neural-ART 選項。
- [Makefile](../firmware/Makefile)、[ai.mk](../firmware/mks/ai.mk)、[kws.mk](../firmware/mks/kws.mk)：連結兩模型、執行環境、MDF 與 CMSIS-DSP；FFT 及前處理物件採一致編譯設定。應用映像排除 .flash_section，該區另輸出為 vision_commands.bin。
- [IDE 建置入口](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh)：專案相對路徑、GCC_PATH 及編譯器版本檢查。

[定版建置日誌](evidence/development-history/deployment_20261008/build.log)與連結腳本可對照下列區域：

| 區域 | 起點／容量 | 該次連結器用量 |
| --- | --- | ---: |
| 應用 SRAM | 0x34000400／1023 KiB | 535,544 位元組 |
| 視覺指令 Flash | 0x71380000／2 MiB | 230,528 位元組 |
| 應用／顯示 PSRAM | 0x91000000／16,128 KiB | 8,949,920 位元組 |
| KWS RAM 保留區 | 0x91FC0000／256 KiB | 顯示 0，產碼另以絕對位址配置 |

KWS 產碼另記錄活化值配置 17,440 位元組，不能將連結器的 0 解讀成不使用 RAM。KWS 權重保留區是 0x70700000／64 KiB；以上保留容量、連結器用量與模型配置量是不同統計，也不是執行期間的全系統記憶體峰值。

[原始產碼與部署證據](evidence/development-history/README.md)保存 ST 工具內部 ONNX 階段、量化中繼資料、11 個硬體及 1 個 CPU Softmax 執行階段、記憶體配置與既有寫入驗證。KWS 控制程式連入應用，沒有獨立 KWS 執行階段控制器指令包。[IDE 同步工具](../tools/ide/README.md)另呈現來源路徑核對、備份、設定變更競態檢查與原子更新。

## 來源與貢獻

本作品使用 ST 範例、HAL／BSP、CMSIS-DSP、FreeRTOS、攝影機中介軟體、STAI／ATON 與官方後處理。工程貢獻涵蓋上述語音資料流程、KWS 訓練與量化、模型介面與建置整合、收音驅動整合、快取一致性、工作協調、工具與驗證；各入口均連到實際程式。

生成係數與模型產碼另標為產物；其配置、匯出與一致性檢查屬於部署流程。來源沿用與自行完成的工程工作一併記錄，詳見[公開內容盤點](publication-review.md)。
