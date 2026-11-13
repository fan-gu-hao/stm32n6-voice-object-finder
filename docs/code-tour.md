# 程式導讀與實作重點

先讀[完整工程流程](engineering-workflow.md)了解跨階段開發，再依下列入口追程式。這份導讀同時涵蓋主機工具、資料、模型與板端系統。

## 1. 從錄音到可訓練資料

| 程式／函式 | 閱讀重點 |
| --- | --- |
| [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) | ELF/BIN 與向量表檢查；RAM 載入；MSP、PC、xPSR、遮罩暫存器設定；main／MicLine 檢查點；偵錯連線清理 |
| [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py)：capture／save | 串列埠獨占、交握重試、帶期限的讀取、音訊標頭、精確位元組數、結尾與 CRC32；WAV 格式、削波統計 |
| [collect_n6.py](../kws/collect_n6.py) | 五類錄音計畫、已完成資料接續、格式與來源資訊 |
| [prepare_dataset.py](../kws/prepare_dataset.py)：speech_regions／extract_word | 短時能量、發音間隔、鄰近單字界線與補零；按原始錄音分組後再切成一秒片段 |

主機工具由 course15 收音階段延續而來；使用它們仍需對應的收音韌體，說明見[工具文件](../kws/recording_tools/README.md)。

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

## 3. 收音驅動、DMA 與環形緩衝

[finder_mic.c](../firmware/Src/finder_mic.c)的 finder_mic_start 配置 MDF1 時脈、GPIO、數位濾波與抽取，以及 GPDMA1 Channel6 的循環鏈結。

HAL_MDF_AcqHalfCpltCallback／HAL_MDF_AcqCpltCallback 每次處理 256 點。receive_block 先處理 DMA 與 CPU 快取一致性，略過暖機區塊，再寫入 32,768 點環形緩衝，以記憶體屏障後發布寫入位置。

finder_mic_take 取得最新 16,000 點快照，以 3,200 點為更新間距。遇到環形跨界分兩段複製；若複製期間被延遲到資料可能遭覆寫則放棄該次快照。錯誤回呼與中斷入口也保留在同一檔案。

## 4. C 前處理、NPU 介面與比對工具

[finder_kws.c](../firmware/Src/finder_kws.c)同時包含正式推論與開發比對：

| 函式／區段 | 閱讀重點 |
| --- | --- |
| 靜態斷言與 finder_kws_init | 核對輸入輸出數量、形狀、INT8 型別及訓練／產碼量化參數 |
| encode_mfcc | 去直流、480 點窗／320 點位移、512 點實數 FFT、功率頻譜、40 個 Mel 濾波器、13 維 DCT、標準化、截限與量化 |
| kws_begin_input_update | CPU 寫新輸入前先清理 NPU 的 64-byte 快取列，再讓 CPU 舊副本失效並執行屏障 |
| prepare_input_cache | 寫入後按 CPU 快取列對齊清理，供 NPU 讀取 |
| finder_kws_classify | 非同步執行狀態與等待事件，區分 MFCC／模型時間，讀取量化輸出並準備下一次推論 |
| finder_kws_compare | 先以參考 INT8 特徵直接測推論，再用參考 PCM 測前處理＋推論；輸出 input_diff、input_max、output_max 與 CMP_Q |
| finder_kws_live_capture／live_send | 依音訊能量選窗，將 PCM、實際 INT8 特徵與輸出成套回傳，附偏移與 CRC32 |

[比對開關](../firmware/Inc/finder_kws_compare.h)在定版中關閉；程式保留供理解當時的部署驗證方法。前處理係數與參考資料分別見 [finder_kws_tables.h](../firmware/Inc/finder_kws_tables.h)及 [finder_kws_compare_data.h](../firmware/Inc/finder_kws_compare_data.h)。

## 5. 雙模型、即時工作與狀態一致性

[app.c](../firmware/Src/app.c)以 nn_thread_fct、dp_thread_fct、isp_thread_fct 分工。推論工作依序執行 KWS 與 YOLO；攝影機緩衝透過計數號誌交接，顯示資料以互斥鎖與遮罩快照協調。

finder_voice_poll 包含峰值、分數、分差、連續命中、最短間隔及安靜後重新啟用的完整狀態機。finder_select_target 更新目標與世代編號；推論若在途中遇到目標改變，舊結果不會覆蓋新狀態。視覺端再以目標類別與連續框 IoU 判定 FOUND。

視覺後處理的輸入適配、模型庫修補及前期轉換證據見[工程流程](engineering-workflow.md)。本版以官方 NMS／遮罩重建為核心，應用層完成選擇目標、結果確認、座標繪製與顯示整合。

## 6. 啟動、記憶體、產碼與建置

- [main.c](../firmware/Src/main.c)：時脈、NPU、CPU 快取、外部記憶體、UART 與作業系統初始化。
- [app_cam.c](../firmware/Src/app_cam.c)：攝影機管線及模型輸入介面。
- [連結腳本](../firmware/Gcc/STM32N657xx.ld)：應用 SRAM、視覺命令 Flash、顯示／後處理 PSRAM，並保留 KWS 專用 RAM。
- [KWS 產碼設定](../kws/deployment/README.md)：獨立模型名稱、RAM／Flash 位址及 Neural-ART 選項。
- [Makefile](../firmware/Makefile)、[ai.mk](../firmware/mks/ai.mk)、[kws.mk](../firmware/mks/kws.mk)：模型、執行環境、CMSIS-DSP 與韌體連結，視覺命令資料分段輸出。
- [IDE 建置入口](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh)：專案相對路徑、GCC_PATH 及編譯器版本檢查。

部分模型暫存由產碼以絕對位址配置，須對照記憶體池與產碼報告；單看連結器的 KWS_RAM 用量會漏掉這部分。

## 來源與貢獻

本作品使用 ST 範例、HAL／BSP、CMSIS-DSP、FreeRTOS、攝影機中介軟體、STAI／ATON 與官方後處理。工程貢獻涵蓋上述資料流程、模型訓練與量化、部署介面修補、驅動整合、快取一致性、工作協調、工具與驗證；各入口均連到實際程式。

生成係數與模型產碼另標為產物；其配置、匯出與一致性檢查屬於部署流程。來源沿用與自行完成的工程工作一併記錄，詳見[公開內容盤點](publication-review.md)。
