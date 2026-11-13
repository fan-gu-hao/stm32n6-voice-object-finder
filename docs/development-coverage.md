# 從起步到定版：工程工作與證據對照

本頁把前期視覺作品、獨立收音與雙模型找物串成工程歷程。階段編號用於閱讀，不代表已知的工時比例或完成百分比。原始模型、量化、移植、失敗案例、修正、驗證與封存均屬工程成果；某個實驗最後沒有採用，也保留其版本和結果。

本輪核對基準：雙模型 `a18c48ebde80370ba29f8649232e58f65fbe49ad`、視覺 `a427ca1b8ba5914a3c5c760ddd22c77899c1fd51`，以及已提供的原專案文件和 67 項原始材料。這是**可取得材料的覆蓋盤點**；尚未取得整個 STM32N6 專案的所有歷史對話及早期專案完整清單，不能宣稱歷史實作已經百分之百無遺漏。

閱讀狀態：**已定位**表示找到具體程式或原始紀錄；**部分定位**表示只有部分材料或既有文件摘要；**待取得**表示尚不能核對，並不表示沒有做過。已定位也不等於每項操作都有完整原始腳本、能在新環境直接重跑。

## 0. 環境起點與前期承接

| 工作 | 已確認的內容 | 證據入口與覆蓋狀態 |
| --- | --- | --- |
| 開發工具與版本 | 後期使用的 IDE、GCC、ST Edge AI、Neural-ART、CubeProgrammer、HAL、RTOS 及 Python 環境 | [建置說明](build.md)、[視覺環境](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/requirements)。**部分定位**：版本快照不等於最初安裝、依賴衝突與排錯全歷程 |
| 前期 COCO 80 類偵測 | course14 腳本沿用 course13 的模型匯出與模型庫環境 | [視覺工程流程](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md)。**部分定位**：course13 自身修改、模型處理與實測的完整歷史尚缺 |
| 更早板級啟用／模型實驗 | 目前不能由後期程式存在某個驅動或演算法，反推當時完成哪些獨立實驗 | **待取得**早期對話、實際專案清單與修改紀錄；先確認哪些工作確實承接本題，不因名稱相近便納入 |

## 1. 視覺模型從電腦到 N6

以下入口位於[視覺作品](https://github.com/fan-gu-hao/stm32n6-instance-segmentation)，細項及原始材料見[工作索引](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md)。各項均已定位，原始臨時操作程式的缺口另列於後文。

| 工作 | 實作內容與工程意義 | 主要公開材料 |
| --- | --- | --- |
| 原始模型基準 | 確認 YOLOv8n-seg 的類別、框與遮罩；圖片及攝影機功能檢查 | `docs/pc_baseline.md`、`scripts/pc_webcam.sh` |
| 模型格式轉換 | 上游預訓練 `.pt` → ONNX → onnx2tf → SavedModel／TFLite | `results/checkpoints/2026-09-09/logs/03_export_seg.log` |
| ST INT8 量化 | 使用校正影像執行逐通道量化，區分匯出工具 INT8 與正式 ST INT8 模型 | `configs/yolov8n_seg_int8_int8.yaml`、`04_st_quantization_seg.log` |
| 介面與三模型比較 | 核對形狀、型別、尺度、零點；比較原始模型、浮點 TFLite 與 ST INT8 | `results/quantization/`、`scripts/check_seg_models_pc.sh`、`results/pc_tflite_check/` |
| 後處理輸出適配 | 修改模型庫設定產生器，按形狀識別偵測與遮罩原型，檢查類別、係數、型別及大小條件 | `patches/modelzoo_seg_output_mapping.patch`、`tools/model_zoo_overrides/` |
| 產碼前自動檢查 | 檢查 80 類、1344 候選、32 遮罩係數、64×64 原型、量化參數與模型雜湊 | `scripts/check_n6_seg_header.py`、`results/deployment_precheck/` |
| 本機產碼流程修補 | 傳入 Neural-ART 配置、記憶體池、輸入輸出格式並處理參數引號 | `patches/modelzoo_n6_local_benchmark.patch`、`scripts/n6_benchmark_local.sh` |
| NPU 編譯與配置 | ST Edge AI 從 TFLite 產生內部 ONNX／量化資訊，再由 Neural-ART 產生模型程式、權重與指令資料 | `results/checkpoints/2026-09-09/n6_deployment/`、`docs/session_2026-09-09.md` |
| 執行期與連結整合 | 對齊模型產碼、執行期函式庫、指令區段與後處理暫存區 | 韌體 `.cproject`／連結腳本、`patches/a1_source_20260918/dependencies.json` |
| 啟動映像與實板部署 | 修正映像標頭／對齊參數，選擇 ST-LINK、建置與寫入並保存結果 | `patches/instance_segmentation_signing_alignment.patch`、`scripts/deploy_n6_seg.sh` |

這裡有兩個不同的 ONNX 階段：原始模型匯出，以及 ST 編譯器內部轉換。量化模型的 INT8 輸入與 N6 產碼的 UINT8／NHWC 介面也分層記錄。後處理適配是實際工程工作；NMS 與遮罩重建核心仍沿用 ST，沒有描述為自行發明的演算法。

## 2. 視覺系統、除錯與驗證

| 工作 | 已完成並保存的內容 | 公開入口與版本界線 |
| --- | --- | --- |
| 相機與顯示整合 | 顯示持續擷取、模型單次擷取、同步推論、後處理、LCD 與快取維護 | 視覺 `firmware/`、工作索引；正式視覺作品為主迴圈與中斷回呼 |
| 結構化串列輸出 | FRAME／DET／END、類別／信心／框／遮罩像素統計、共同影格序號 | `patches/uart_inference_result.patch` |
| 人物區域狀態機 | 框底邊中心判斷、連續幀進入／離開、計數與畫面狀態 | `project_region_event.h`、區域事件修補 |
| 有效性與故障處理 | 檢查物件、座標與分數；逾時／錯誤時清舊框、回報失效並停止發布 | 區域事件模組及 A5；失效不等於正常離開，等待人工重設 |
| 效能量測插樁 | 影格序號、擷取時間、推論／後處理／UART／顯示／快取／完整週期及日誌成本 | `docs/a3_performance_20260918/instrumentation/` |
| UART 中斷試驗 | 環形佇列、完整列提交、重要訊息預留、短臨界區、記憶體屏障、回呼、統計與 HAL 相依修復 | [歷史 C/H、兩版安裝及部署／還原](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/docs/publication_supplement_20261113/uart_it)；正式版未採用，無獨立加速結論 |
| A1 來源與重建 | 固定上游、修改／新增／刪除與相依資訊；來源隔離還原、既有環境乾淨重建、燒錄讀回 | `docs/a1_reproducible_20260918/`；隔離還原目錄只核對來源，不等於在該目錄重建 |
| A2 固定輸入與數值診斷 | 同像素、原始張量、量化誤差、框／分數／係數拆解、電腦後端差異 | `docs/a2_validation_20260918/`、補充材料 `a2/` |
| A2 框／遮罩及 50 張回歸 | 共同後處理、一對一配對、標註與最差案例、排除重疊影像、誤檢漏檢追查 | 同上；不宣稱板端 C 後處理逐像素等價或完整 COCO 準確率 |
| A3 效能分析 | 有人／無人完整週期、暖機後重複推論、逐區塊分析、輸出核對與計時來源 | `docs/a3_performance_20260918/`；模型呼叫與端到端週期分開 |
| A4 記憶體實驗 | 固定其他條件調整 npuRAM6 容量、比較實體池配置、兩版計時與輸出回歸 | `docs/a4_memory_20260918/`；實驗配置未取代正式相機版本，微小時間差不稱加速 |
| A5 冷啟動與狀態測試 | 冷啟動、序號同步、受控進出及畫面確認 | `docs/a5_acceptance_20260919/`；僅對應視覺作品 |
| A5 長測與故障注入 | 保留首輪異常、分析序號、重新量測；軟體模擬擷取通知逾時，恢復正式映像並核對 | 同上及補充材料 `a5/`；首輪異常根因未確定，不抹去失敗紀錄 |

## 3. 音訊資料從板子到訓練集

| 工作 | 實作內容 | 已定位的公開入口 |
| --- | --- | --- |
| 獨立收音韌體 | 從官方播放範例改為五秒 RAM 錄音；DMA 半滿／全滿複製、暖機、逾時、錯誤、長度與 CRC32 | [錄音 FSBL 與上游差異](../kws/recording_firmware/README.md) |
| RAM 啟動與偵錯 | ELF／BIN、堆疊與入口向量檢查、版本字串、載入、核心狀態、中斷點及解除偵錯連線 | [主機工具](../kws/recording_tools/README.md) |
| 錄音協定與接收 | 串列獨占、查詢／開始交握、固定長度、結尾、逾時與 CRC32；WAV 格式及削波統計 | [n6_receive_wav.py](../kws/recording_tools/n6_receive_wav.py) |
| 分類資料收集 | cup／bottle／phone／unknown／silence 計畫、來源與工作階段、格式核對及中止後接續 | [collect_n6.py](../kws/collect_n6.py) |
| 切段與分組 | 短時能量定位發音、一秒片段與補零、相鄰發音邊界；先依原始錄音分組再切片 | [prepare_dataset.py](../kws/prepare_dataset.py) |
| 連續收音移植 | MDF／GPDMA 循環鏈結、時脈與存取屬性、DMA 快取、環形緩衝及滑動視窗 | [finder_mic.c](../firmware/Src/finder_mic.c) |
| 原始即時視窗回傳 | 同一 PCM、INT8 特徵與模型輸出封包、分段十六進位及 CRC32，供分層比對 | [finder_kws.c](../firmware/Src/finder_kws.c) |
| 現場資料迭代 | 收集清單、標籤、訓練／保留用途、逐段 PCM 雜湊 | [48 段資料清單](evidence/development-history/live_dataset_manifest_20261008.json) |

## 4. KWS 從特徵到 NPU

| 工作 | 實作內容 | 已定位的公開入口 |
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

## 5. 雙模型系統整合

| 工作 | 實作內容 | 已定位的公開入口 |
| --- | --- | --- |
| 框架移植 | 以 ST 手部雙模型 FreeRTOS 框架為基礎，改接 YOLO 與 KWS | [來源紀錄](source-provenance.json)、[app.c](../firmware/Src/app.c) |
| 模型共用 NPU | 在同一推論工作依序輪詢 KWS 與執行 YOLO，顯示及 ISP 由其他工作協作 | `nn_thread_fct`／`dp_thread_fct`／`isp_thread_fct` |
| 相機輸入適配 | 把上游手部模型的寬高比處理改為中央正方形區域，再縮放到模型輸入 | [app_cam.c](../firmware/Src/app_cam.c) |
| 目標選擇與語音接受 | 三種物件、音量／分數／分差、連續視窗、命令間隔、安靜後重啟用、USER1 操作 | `finder_voice_poll`、`finder_select_target` |
| 跨工作一致性 | 目標世代防止切換後發布舊結果、框的連續幀 IoU、遮罩快照與顯示互斥 | [app.c](../firmware/Src/app.c) |
| 記憶體與建置 | 應用 SRAM、顯示／後處理 PSRAM、視覺指令區、KWS 專用 RAM／Flash；MDF、DSP、兩模型共同連結 | [連結腳本](../firmware/Gcc/STM32N657xx.ld)、[建置清單](../firmware/mks/kws.mk) |
| 診斷與降級行為 | 啟動／推論錯誤、語音與搜尋狀態、收音統計、手動切換路徑 | [app.c](../firmware/Src/app.c)、[finder_mic.c](../firmware/Src/finder_mic.c) |

視覺持續執行，語音改變搜尋目標。三工作能交錯執行，不代表兩模型同時占用 NPU。底層時脈、AXISRAM、GPU2D、RIF、UART 與 FreeRTOS 啟動主要沿用上游；本作品的價值包含選用、適配與整合，不能把整份框架描述為自行重寫。

### 已公開程式中，應具體呈現的整合細節

這些程式本來已公開，本輪補的是工程說明，不是新增韌體功能。下列涉及故障的描述是原始碼設計；沒有因此宣稱新增故障注入測試。

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
| DSP 編譯一致性 | FFT 物件與前處理物件採相同編譯設定，配合此版 CMSIS-DSP 路徑 | [kws.mk](../firmware/mks/kws.mk)；不描述為自行實作 FFT 或 MVE 最佳化 |

上游差異對照另確認：`main.c` 的修改集中於模型標頭與啟動資訊；`FreeRTOSConfig.h` 與 ST 基底相同。三工作、靜態配置、相機佇列與部分中斷交接原本已存在，本版新增的是音訊／視覺應用與新的資料／狀態交接。這種來源區分保留實際整合工作，也避免誇大底層元件的作者歸屬。

## 6. 定版、IDE 與公開交付

| 工作 | 保存內容 | 覆蓋狀態 |
| --- | --- | --- |
| 五映像分工 | FSBL、應用、視覺權重、KWS 權重、視覺指令；記錄位址及雜湊，分開抽取 ELF 區段 | [工程流程](engineering-workflow.md)、[來源與證據](evidence/development-history/README.md)。五映像不是五個模型 |
| 既有建置與寫入 | 定版建置報告、應用與 KWS 權重寫入及驗證紀錄 | [部署紀錄](evidence/development-history/deployment_20261008/)。已定位 |
| 封存前重建核對 | 原專案 README 記載：獨立暫存重建、應用差異為編譯時間字元、視覺指令一致 | **部分定位**：是既有文件記載，完整原始核對日誌尚未在本輪材料定位，不稱本輪重測 |
| 來源與版本封存 | 原本 firmware／vision 來源、模型版本、訓練快照、本機整合 Git、定版包與雜湊 | [來源紀錄](source-provenance.json)、[訓練快照](../kws/training_snapshot/README.md)；公開庫與本機完整封存的範圍不同 |
| IDE 來源同步 | linked resources、路徑核對、預覽、備份、雜湊競態檢查、原子替換、編譯器入口 | [同步工具](../tools/ide/README.md)、[建置說明](build.md) |
| 公開整理 | 來源聲明、程式導覽、證據索引、模型／映像公開界線、提交與同步 | [材料盤點](publication-review.md)、[第三方說明](../THIRD_PARTY_NOTICES.md) |
| 展示影片 | 預定補拍整合系統的實際操作 | 待補；不以其他版本的測試代替 |

獨立錄音範例的 FSBL 原始碼與整合系統採用的官方預建啟動 FSBL 是不同材料；公開前者不代表後者已具完整建置來源。映像的無金鑰標頭封裝不描述為密碼學簽章。

## 仍需取得的歷史材料

| 缺口 | 已有內容 | 尚缺內容及核對方式 |
| --- | --- | --- |
| 全部專案對話 | 當前對話、部分摘要、附件與公開紀錄 | STM32N6 專案各聊天完整原文，包含實際執行結果；逐項區分建議、已執行、失敗、修正及放棄的方案 |
| 起步與 course13 | 後期環境版本、course14 沿用環境路徑 | 實際早期專案清單、course13 模型庫修改及未指定目錄中的資料；不能靠猜測資料夾名稱證明沒有遺漏 |
| 臨時終端程式 | 匯出／量化、A1～A5、KWS 係數／接收／分析的設定、方法與結果 | 未另存檔的原始終端程式須從完整對話或既有紀錄恢復；若日後重建，須標明為重建版本 |
| 固定 INPUT／PCM 比較 | 板端比較程式、電腦 reference.json、既有摘要 | 原始板端 CMP 逐列日誌；電腦參考 JSON 不能代替板端輸出 |
| 音訊與訓練早期實跑 | 錄音／切段工具、四版訓練來源、最終評估與現場清單 | 最初錄音啟動／接收日誌、原始切段清單及各次中間訓練的完整結果；不能由程式存在推定每次實跑結果 |
| 早期三映像寫入與封存前重建 | 原 README 記載 2026-10-04 三映像寫入及封存前核對，最終應用／KWS 日誌已公開 | 早期寫入日誌與完整重建比較原文；各自定位後再提升證據層級 |

上次 67 項收集程式有掃 course13／course15 根目錄中符合副檔名的檔案，再遞迴指定的 scripts、tools、configs、patches、docs。報告沒有 course13 檔案項目，也明確排除了模型庫等目錄；它不是整個 STM32N6 工作目錄的完整清單。指定目錄不存在，不能推論該階段沒有工程工作。

沒有新增訓練、建置、燒錄或硬體驗收。模型權重、原始錄音、模型產碼和預建映像仍依既定公開範圍處理；其未公開不等於沒有描述所做工作。下一次歷史補全依實際取得的原文與檔案擴充本頁，不把目前已定位的項目數當成整個專案的總數。
