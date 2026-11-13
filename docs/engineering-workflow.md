# 完整開發流程、跨階段延續與實作證據

本作品的工程範圍涵蓋模型部署、音訊驅動、資料製作、模型訓練與量化、Python／C 對照、NPU 整合、即時作業系統排程、快取與記憶體配置，以及映像交付。這些工作分階段完成，部分先在其他課程專案與開發對話中驗證，再沿用至雙模型找物系統。

## 開發脈絡

| 階段 | 累積的工作 | 本作品如何延續 |
| --- | --- | --- |
| 前期 YOLO 偵測 | COCO 類別模型的匯出、量化與 N6 工具環境 | 建立後續分割模型部署的工具與流程；課程 14 的部署腳本保留前期環境路徑 |
| course14 實例分割 | PyTorch → ONNX → onnx2tf／SavedModel → ST INT8；模型輸出對應修補、攝影機與 LCD、UART、固定輸入回歸、效能與記憶體實驗 | 延續視覺模型介面、後處理移植、部署、記憶體及除錯經驗；[完整程式與證據](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| course15 板上收音 | MDF 錄音、RAM 載入與啟動檢查、UART 交握、完整長度與 CRC32 校驗、WAV 保存 | [主機錄音工具](../kws/recording_tools/README.md)已納入本庫；連續收音實作進一步整合在 finder_mic.c |
| course17 雙模型 | 自行蒐集資料、MFCC、KWS 訓練與量化、板端比對、現場補樣本及分組交叉驗證 | KWS 與 YOLO 在 FreeRTOS 下整合為語音選擇搜尋目標的系統 |

本頁同時保留「完成過哪些工程工作」與「本版實際使用哪個產物」兩條線。課程 14 自行量化模型的歷史 SHA-256 為 312ea45821140094d6a637d11f2e7daf1c8eb3e9ad5f93b8ed6c595128eaec2e；本版視覺模型的來源與 33167331… 雜湊記錄於 [sources.txt](../sources.txt)。前期自行量化與模型庫修補的成果仍由上表連到原始證據。

## 視覺模型匯出、量化與後處理延續

前期分割作品已保存[匯出成功日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log)：ONNX 1.16.1／opset 19 匯出 yolov8n-seg.onnx，再由 onnx2tf 1.26.3 與 TensorFlow 2.18.0 產生 SavedModel／TFLite。ST 逐通道量化另有[設定](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/configs/yolov8n_seg_int8_int8.yaml)與[成功日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/04_st_quantization_seg.log)。

[Model Zoo 修補](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/patches/modelzoo_seg_output_mapping.patch)依張量形狀辨識 1×116×1344 偵測資料與 1×64×64×32 遮罩原型，並驗證型別、類別數、遮罩係數及輸出大小；另完成本機 Neural-ART 產碼參數與映像對齊修補。這些屬於已完成的部署與後處理介面工程。

本雙模型版本將視覺產碼與 ST 後處理接入手部雙模型範例的 FreeRTOS 框架，再加入目標選擇、連續幀確認與狀態顯示。[app.c](../firmware/Src/app.c)、[後處理轉接層](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c)、[建置清單](../firmware/mks/ai.mk)保存這一版的整合入口。

## 音訊、訓練與板端部署的逐步工作

| 階段 | 實際工作與工程重點 | 可閱讀的實作 |
| --- | --- | --- |
| 1. 收音韌體啟動工具 | 找出 IDE 偵錯工具；檢查 ELF/BIN、堆疊與入口向量、錄音版本字串；RAM 載入後設定核心狀態，以 main／MicLine 中斷點核對，再解除偵錯連線 | [n6_mic_start_and_record.sh](../kws/recording_tools/n6_mic_start_and_record.sh) |
| 2. 錄音傳輸 | 串列埠獨占、查詢交握、開始錄音、固定長度讀取、逾時、結尾標記、CRC32、WAV 格式與削波統計 | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| 3. 原始資料蒐集 | 依 cup／bottle／phone／unknown／silence 計畫錄音；格式檢查、來源與工作階段資訊、已完成片段接續 | [collect_n6.py](../kws/collect_n6.py) |
| 4. 切段與資料分組 | 以短時能量切出發音；一秒片段補零、避免切入相鄰單字；先按五秒原始錄音分訓練／驗證，再切短片段 | [prepare_dataset.py](../kws/prepare_dataset.py) |
| 5. 音訊特徵 | Python 實作去平均值、週期 Hann 窗、FFT、HTK Mel 濾波器、對數及正交 DCT；保留前處理係數 | [定版 train_kws.py](../kws/training_snapshot/train_kws.py) |
| 6. 客製 KWS 模型 | 建立 49×13×1 輸入的深度可分離卷積網路；五分類、資料增強、類別權重與訓練紀錄 | [網路架構與資料增強](../kws/training_snapshot/train_kws.py) |
| 7. 現場資料迭代 | 保存即時資料重訓版本；按發音能量選取板上視窗、加入實際底噪與現場語音，與保留資料分開 | [live v3 訓練程式](../kws/train_kws_live_v3.py)、[收集計畫](../kws/live_collection_plan.json)、[板端擷取](../firmware/Src/finder_kws.c) |
| 8. 防止資料洩漏 | 依原始錄音分組；PCM 雜湊識別相同音訊並合併組別；拒絕開發與保留測試重複；每折的標準化及背景噪音僅取訓練組 | [load_development／make_splits／make_training](../kws/training_snapshot/train_kws_groupcv.py) |
| 9. 分組交叉驗證 | 分層分組五折驗證、選擇訓練輪數，再訓練最終模型；保留 16 段現場音訊另評估 | [定版分組訓練](../kws/training_snapshot/train_kws_groupcv.py)、[五折報告](evidence/kws-groupcv.json) |
| 10. KWS 量化與匯出 | 以代表資料集將 Keras／SavedModel 轉為 INT8 TFLite；保存尺度、零點、特徵係數及浮點／量化結果 | [export_int8](../kws/training_snapshot/train_kws_groupcv.py)、[保留音訊報告](evidence/kws-int8-holdout.json) |
| 11. N6 模型產碼 | 為 KWS 設定專用 RAM／Flash、產碼選項與獨立網路名稱，與視覺模型共同連結 | [產碼配置](../kws/deployment/README.md)、[kws.mk](../firmware/mks/kws.mk) |
| 12. 連續收音驅動整合 | MDF1 時脈／腳位／濾波與抽取，GPDMA 循環鏈結、半滿／全滿回呼；暖機後寫入環形緩衝，取得一秒滑動視窗 | [finder_mic.c](../firmware/Src/finder_mic.c) |
| 13. CPU／DMA 一致性 | DMA 緩衝與描述節點對齊；快取清理／失效與記憶體屏障；快照複製若被延遲至資料可能覆寫則捨棄 | [cache_prepare／receive_block／finder_mic_take](../firmware/Src/finder_mic.c) |
| 14. C 前處理與模型介面 | CMSIS-DSP FFT 與 C MFCC，標準化、截限、INT8 量化；靜態檢查形狀與型別，初始化時核對訓練與產碼尺度、零點 | [finder_kws.c](../firmware/Src/finder_kws.c)、[係數表](../firmware/Inc/finder_kws_tables.h) |
| 15. CPU／NPU 一致性 | CPU 寫新輸入前，先處理 NPU 快取與 CPU 舊副本；寫入後清理 CPU 快取；等待非同步推論完成並重設下一次推論狀態 | [kws_begin_input_update／prepare_input_cache／finder_kws_classify](../firmware/Src/finder_kws.c) |
| 16. 分層比對與除錯 | 固定 INT8 輸入直接測模型，再由同一 PCM 測完整 C 前處理；比較輸入差異與輸出量化值 | [finder_kws_compare](../firmware/Src/finder_kws.c)、[比對設定](../firmware/Inc/finder_kws_compare.h) |
| 17. 即時原始資料回傳 | 保存同一視窗的 PCM、637 個 INT8 特徵與五個輸出，以分段十六進位及 CRC32 回傳供電腦比對 | [finder_kws_live_capture／live_send](../firmware/Src/finder_kws.c) |
| 18. 語音接受狀態機 | 音量、最高分、與次高分差距、連續視窗、命令間隔、安靜後重新啟用；同一持續發音只接受一次 | [finder_voice_poll](../firmware/Src/app.c) |

KWS 的訓練路線是 Keras／SavedModel → INT8 TFLite → ST Edge AI／Neural-ART，與前期 YOLO 的 ONNX 匯出路線分別記錄。這裡的「分組」以原始錄音和 PCM 內容為單位，沒有把它描述成未執行的跨說話者驗證。

## 即時系統、記憶體與交付工作

| 工作 | 實作內容 | 入口 |
| --- | --- | --- |
| 雙模型排程 | 單一推論工作依序輪詢 KWS 與執行 YOLO，共用 NPU；顯示與 ISP 為另外的工作 | [nn_thread_fct／dp_thread_fct／isp_thread_fct](../firmware/Src/app.c) |
| 攝影機與顯示協作 | DCMIPP 顯示與推論管線、雙輸入緩衝、計數號誌、顯示互斥鎖、遮罩快照及快取維護 | [app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c) |
| 目標與狀態一致性 | 接受語音或按鍵後切換類別；用目標世代編號捨棄推論途中切換前的舊結果；連續框 IoU 確認後顯示 FOUND | [finder_select_target 與推論結果發布](../firmware/Src/app.c) |
| 開機整合 | 時脈、NPU、CPU 快取、外部記憶體、UART、顯示與 FreeRTOS 初始化 | [main.c](../firmware/Src/main.c) |
| 記憶體區隔 | 應用 SRAM、顯示與後處理 PSRAM、獨立視覺指令區；保留 KWS RAM 0x91FC0000／256 KiB、權重 Flash 0x70700000／64 KiB | [連結腳本](../firmware/Gcc/STM32N657xx.ld)、[KWS 記憶體池](../kws/deployment/kws.mpool) |
| 建置整合 | 納入兩模型、HAL MDF、CMSIS-DSP 與執行環境；統一 FFT 相關編譯設定；將 .flash_section 分開輸出 | [Makefile](../firmware/Makefile)、[kws.mk](../firmware/mks/kws.mk)、[ai.mk](../firmware/mks/ai.mk) |
| IDE 整理 | 同步來源與標頭的瀏覽／建置入口，以專案位置解析路徑，支援 GCC_PATH 並核對 GCC 14.3.1 | [IDE 專案](../firmware/STM32CubeIDE/STM32N6570-DK/.project)、[IDE 建置入口](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) |
| 定版與交付 | 保存來源版本、模型與工具設定、訓練快照、五映像的本機定版包及既有寫入驗證紀錄 | [來源紀錄](source-provenance.json)、[結果](results.md)、[建置說明](build.md) |

KWS 產碼沒有啟用 epoch controller（執行階段控制器）；CPU 執行模型控制流程，NPU 仍執行對應硬體運算。控制程式連入主應用，另配置語音權重；沒有獨立 KWS ecblob 映像。這是本版的配置選擇，沒有宣稱做過 EC 開關效能比較。

本機五映像包分別包含 FSBL、應用、視覺權重、KWS 權重、視覺執行指令；不是五個 AI 模型。映像封裝工具使用無金鑰模式（-nk），因此不把封裝標頭描述成密碼學簽章。

## 驗證歷程與公開範圍

[結果說明](results.md)區分早期部署比對、現場資料改進與最終分組模型，保留已有結果的適用範圍。早期 INPUT／PCM 比對及即時 PCM／特徵回傳，用來區分前處理、部署與模型本身的問題；它們也是工程成果，不只看最後的辨識率。

目前已公開：前期視覺轉換與量化日誌、修改補丁、A1～A5；本作品的音訊、訓練、比對／即時擷取程式、配置與離線評估報告。板上原始語音日誌、早期比較報告和 course15 收音韌體仍在本機，已在[公開內容盤點](publication-review.md)列出，避免把「尚未附原始檔」誤寫成「未做過」。

上游 HAL、BSP、CMSIS-DSP、RTOS、模型架構、推論執行環境與後處理演算法保留來源聲明。模型轉換、參數選擇、介面修補、驅動整合、資料流程、快取處理、排程、除錯與驗證則在本頁逐一列明。模型權重與預建映像的公開範圍見 [第三方來源說明](../THIRD_PARTY_NOTICES.md)。
