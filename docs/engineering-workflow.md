# 雙模型語音找物：從資料建立到 N6 部署

[繁體中文](engineering-workflow.md) | [English](engineering-workflow.en.md)

本專案在 STM32N6570-DK 上建立關鍵字辨識（Keyword Spotting，KWS）與 YOLOv8 實例分割的雙模型系統。工程流程涵蓋資料蒐集、梅爾頻率倒譜係數（MFCC）前處理、客製模型訓練與 INT8 量化、N6 模型產碼、電腦／板端數值對照，以及 FreeRTOS 下的音訊、視覺與顯示整合。

視覺持續辨識攝影機畫面；語音命令 cup、bottle、phone 改變搜尋目標。兩個模型在同一推論工作中依序使用神經網路處理器（NPU），顯示與影像訊號處理（ISP）由另外兩個工作協作。[實作與證據索引](development-coverage.md)列出各步驟對應的程式、設定與結果。

## 系統建立與模型分工

| 階段 | 本專案完成的工作 | 實作入口 |
| --- | --- | --- |
| 平台與應用框架 | 固定 GCC、ST Edge AI、Neural-ART 與執行期版本，將 ST 雙模型 FreeRTOS 框架改接語音與視覺模型 | [建置環境](build.md)、[來源紀錄](source-provenance.json)、[app.c](../firmware/Src/app.c) |
| 語音資料蒐集子系統 | MDF／DMA 五秒錄音、RAM 啟動、UART 交握及 CRC32、WAV 保存、分類收集與切段 | [錄音韌體](../kws/recording_firmware/README.md)、[主機工具](../kws/recording_tools/README.md)、[collect_n6.py](../kws/collect_n6.py) |
| KWS 模型建立 | 自行蒐集五分類資料、MFCC、深度可分離卷積、資料增強與分組交叉驗證，匯出 INT8 模型 | [訓練快照](../kws/training_snapshot/README.md)、[訓練演進](../kws/training_history/README.md) |
| 兩模型部署與整合 | KWS 產碼、既有量化 YOLO 模型介面、ST 後處理、記憶體區隔、共享 NPU 與搜尋狀態 | [KWS 部署](../kws/deployment/README.md)、[app.c](../firmware/Src/app.c)、[連結腳本](../firmware/Gcc/STM32N657xx.ld) |

## 本系統的視覺模型介面與後處理整合

視覺使用 [sources.txt](../sources.txt) 固定來源與雜湊的 ST 量化模型 `yolov8n_256_quant_pc_ii_seg_coco-st.tflite`，SHA-256 為 `3316733125a5fb85d66ed33993627b5d293b3baceb348b137132071ca365ebd6`。本專案將其 N6 產碼、ST 推論執行期與實例分割後處理接入雙模型應用，並配置模型輸入、輸出與指令區。

| 介面／處理 | 整合方式 |
| --- | --- |
| 攝影機輸入 | 從顯示視野取中央正方形，縮放成 `256×256 RGB UINT8`；檢查輸入大小與型別 |
| 模型輸出 | 兩組 INT8 張量分別承載 `1×116×1344` 偵測資料與 `1×64×64×32` 遮罩原型；沿用 ST 轉接層辨識輸出並取得量化參數 |
| 後處理 | 接入 ST 解碼、非極大值抑制（NMS）與遮罩生成；信心門檻 0.50、NMS 交併比（IoU）0.40、最多 10 個結果 |
| 搜尋目標 | 從 80 類結果篩選 cup=41、bottle=39、cell phone=67；選最高信心框，連續兩幀且框 IoU 至少 0.30 才發布 FOUND |
| 顯示適配 | 將框與遮罩映射回液晶螢幕（LCD）中央方形區域；保存遮罩快照，避免下一輪後處理覆寫顯示資料 |

[app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c)、[後處理轉接層](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c)及[建置清單](../firmware/mks/ai.mk)保存這些整合入口。NMS 與遮罩重建演算法保留 ST 來源，本專案實作模型接入、目標與狀態管理、座標適配及跨工作資料交接。

## 音訊、訓練與板端部署的逐步工作

最前面的資料蒐集先使用[獨立收音 main.c](../kws/recording_firmware/FSBL/Src/main.c)：DMA 半滿／全滿回呼把樣本複製至 RAM，略過暖機區塊，主迴圈處理逾時、停止 DMA、CRC32 與串列傳輸。這份來源及上游修改已與主機工具一起保存。

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
| 11. N6 模型產碼 | 為 KWS 設定專用 RAM／Flash、產碼選項與獨立網路名稱，經工具內部 ONNX 再由 Neural-ART 編譯，與視覺模型共同連結 | [產碼配置](../kws/deployment/README.md)、[原始命令與報告](evidence/development-history/README.md)、[kws.mk](../firmware/mks/kws.mk) |
| 12. 連續收音驅動整合 | MDF1 時脈／腳位／濾波與抽取，GPDMA 循環鏈結、半滿／全滿回呼；暖機後寫入環形緩衝，取得一秒滑動視窗 | [finder_mic.c](../firmware/Src/finder_mic.c) |
| 13. CPU／DMA 一致性 | DMA 緩衝與描述節點對齊；快取清理／失效與記憶體屏障；快照複製若被延遲至資料可能覆寫則捨棄 | [cache_prepare／receive_block／finder_mic_take](../firmware/Src/finder_mic.c) |
| 14. C 前處理與模型介面 | CMSIS-DSP FFT 與 C MFCC，標準化、截限、INT8 量化；靜態檢查形狀與型別，初始化時核對訓練與產碼尺度、零點 | [finder_kws.c](../firmware/Src/finder_kws.c)、[係數表](../firmware/Inc/finder_kws_tables.h) |
| 15. CPU／NPU 一致性 | CPU 寫新輸入前，先處理 NPU 快取與 CPU 舊副本；寫入後清理 CPU 快取；等待非同步推論完成並重設下一次推論狀態 | [kws_begin_input_update／prepare_input_cache／finder_kws_classify](../firmware/Src/finder_kws.c) |
| 16. 分層比對與除錯 | 固定 INT8 輸入直接測模型，再由同一 PCM 測完整 C 前處理；比較輸入差異與輸出量化值 | [finder_kws_compare](../firmware/Src/finder_kws.c)、[比對設定](../firmware/Inc/finder_kws_compare.h) |
| 17. 即時原始資料回傳 | 保存同一視窗的 PCM、637 個 INT8 特徵與五個輸出，以分段十六進位及 CRC32 回傳供電腦比對 | [finder_kws_live_capture／live_send](../firmware/Src/finder_kws.c) |
| 18. 語音接受狀態機 | 音量、最高分、與次高分差距、連續視窗、命令間隔、安靜後重新啟用；同一持續發音只接受一次 | [finder_voice_poll](../firmware/Src/app.c) |

KWS 的完整路線是 Keras／SavedModel → INT8 TFLite → ST Edge AI 內部 ONNX 與量化中繼資料 → Neural-ART → N6。[原始產碼日誌](evidence/development-history/codegen_20261008/codegen.log)保留內部 ONNX 檔名與實際編譯器呼叫；此 ONNX 是 ST 工具鏈的內部中介表示。這裡的「分組」以原始錄音和 PCM 內容為單位，沒有把它描述成未執行的跨說話者驗證。

[訓練歷程](../kws/training_history/README.md)另外補入 2026-10-05 初版原檔，呈現早期資料增強、現場補樣本、發音邊界限制，到分組定版的實作演進。[48 段現場收集清單](evidence/development-history/live_dataset_manifest_20261008.json)保存 32 段訓練、16 段保留及逐段 PCM 雜湊。

## 即時系統、記憶體與交付工作

| 工作 | 實作內容 | 入口 |
| --- | --- | --- |
| 雙模型排程 | 單一推論工作依序輪詢 KWS 與執行 YOLO，共用 NPU；顯示與 ISP 為另外的工作 | [nn_thread_fct／dp_thread_fct／isp_thread_fct](../firmware/Src/app.c) |
| 攝影機與顯示協作 | DCMIPP 顯示與推論管線、雙輸入緩衝、計數號誌、顯示互斥鎖、遮罩快照及快取維護 | [app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c) |
| 目標與狀態一致性 | 接受語音或按鍵後切換類別；用目標世代編號捨棄推論途中切換前的舊結果；連續框 IoU 確認後顯示 FOUND | [finder_select_target 與推論結果發布](../firmware/Src/app.c) |
| 開機整合 | 沿用 ST 時脈、NPU、CPU 快取、外部記憶體、UART、顯示與 FreeRTOS 啟動，改接本案模型 | [main.c](../firmware/Src/main.c) |
| 記憶體區隔 | 應用 SRAM、顯示與後處理 PSRAM、獨立視覺指令區；保留 KWS RAM 0x91FC0000／256 KiB、權重 Flash 0x70700000／64 KiB | [連結腳本](../firmware/Gcc/STM32N657xx.ld)、[KWS 記憶體池](../kws/deployment/kws.mpool) |
| 建置整合 | 納入兩模型、HAL MDF、CMSIS-DSP 與執行環境；統一 FFT 相關編譯設定；將 .flash_section 分開輸出 | [Makefile](../firmware/Makefile)、[kws.mk](../firmware/mks/kws.mk)、[ai.mk](../firmware/mks/ai.mk) |
| IDE 整理 | 同步來源與標頭的瀏覽入口，核對既有連結、備份、競態檢查與原子替換；建置入口支援 GCC_PATH 並核對 GCC 14.3.1 | [原始同步工具](../tools/ide/README.md)、[IDE 專案](../firmware/STM32CubeIDE/STM32N6570-DK/.project)、[IDE 建置入口](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh) |
| 定版與交付 | 保存來源版本、模型與工具設定、訓練快照、五映像的本機定版包及既有寫入驗證紀錄 | [來源紀錄](source-provenance.json)、[結果](results.md)、[建置說明](build.md) |

KWS 產碼沒有啟用 epoch controller（執行階段控制器）；CPU 執行模型控制流程，NPU 仍執行對應硬體運算。控制程式連入主應用，另配置語音權重；沒有獨立 KWS ecblob 映像。本版由同一推論工作依序執行兩個模型，控制流程與權重各自按配置連結。

[定版編譯報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)記錄 11 個硬體及 1 個軟體 Softmax 執行階段，權重配置 11,409 位元組、活化值 17,440 位元組。這些是 KWS 編譯統計，與兩個模型整合後的全系統記憶體峰值分開解讀。

本機五映像包分別包含 FSBL、應用、視覺權重、KWS 權重、視覺執行指令；不是五個 AI 模型。映像封裝工具使用無金鑰模式（-nk），因此不把封裝標頭描述成密碼學簽章。

## 驗證與版本對應

| 階段 | 保存的結果 | 適用範圍 |
| --- | --- | --- |
| 前處理與部署比較 | 即時四例 INT8 特徵與電腦完全一致，輸出最大整數差異為 0、0、3、1 | [早期比較模型的原始報告](evidence/development-history/live_comparison_20261007.json)；固定 INPUT／PCM 比較程式另保留在韌體中 |
| 模型與資料問題定位 | 同一 silence 樣本在板端、電腦特徵輸入及完整 PCM 前處理三路皆判成 phone | 同份比較報告；保留失敗案例，與後續現場資料改進分開記錄 |
| 分組定版 | 五折開發驗證 224/227（98.68%）；保留音訊 INT8 15/16（93.75%） | [評估報告](evidence/README.md)；五折用於開發與選輪，保留結果是 16 段單窗離線評估 |
| 定版板上操作 | cup、bottle、phone 各兩次接受；同輪保存的視覺訊息皆為 found=0 | [2026-10-08 日誌](evidence/development-history/voice_groupcv_20261008.log)；統計語音接受，與較早視覺 FOUND 紀錄分開 |
| 部署 | 應用與 KWS 權重的寫入及驗證成功 | [部署清單與紀錄](evidence/development-history/deployment_20261008/)；其餘映像沿用已配置內容 |

完整[結果說明](results.md)依各次模型雜湊與日誌區分版本。展示影片待補；雙模型系統的獨立供電與冷啟動不列為已實測通過。

本庫保存資料蒐集韌體與主機工具、訓練歷程、比對與即時擷取程式、模型配置、整合應用及[原始證據](evidence/development-history/README.md)。HAL、BSP、CMSIS-DSP、FreeRTOS、ST 推論執行期與視覺後處理保留上游來源。模型權重、原始音訊、模型產碼與預建映像的公開範圍及建置依賴見[第三方來源說明](../THIRD_PARTY_NOTICES.md)與[建置文件](build.md)。
