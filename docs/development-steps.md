# 雙模型語音找物：32 個完整開發步驟

[繁體中文](development-steps.md) | [English](development-steps.en.md) | [返回首頁](../README.md)

> **版本編號說明：**`Runtime1100`、`Runtime1200`、`Runtime1201` 分別代表 ST 神經網路執行函式庫（Network Runtime）的 **11.0.0、12.0.0、12.0.1** 版本。這套函式庫在建置時連結進韌體，提供模型程式所需的執行支援；更新模型產碼工具時，也須配對函式庫、標頭檔與神經網路處理器（NPU）支援程式。這些編號與 ST Edge AI 工具本身的版本號分開記錄。 [版本配對詳解](toolchain-compatibility.md)。

本專案在 STM32N6570-DK 上完成語音與視覺協作的微控制器（MCU）級嵌入式人工智慧系統。以下從需求、模型部署、資料與訓練，展開到即時系統、記憶體、數值除錯及工程交付；每一步都連到對應程式、設定或開發紀錄。編號按工程依存關係編排，資料迭代與除錯在實際開發中交錯進行。

除韌體與訓練原始碼外，[開發主機流程](../tools/development-history/README.md)保存原始操作區塊中的封裝診斷、固定比對、即時資料收集、產碼、部署及觀察程式；各檔的來源、依存及當時執行狀態一併記錄。

## 第一階段：需求、工程與視覺模型部署（1–5）

<a id="step-01"></a>
### 1. 定義雙模型展示的功能與操作方式

- 在 STM32N6570-DK 上執行語音與影像推論；板上數位麥克風、攝影機及液晶螢幕（LCD）形成完整操作介面。
- 說出杯子（`cup`）、瓶子（`bottle`）或手機（`phone`），由語音模型選定搜尋目標。攝影機與 YOLOv8 實例分割持續運作，搜尋目前指定的物件。
- LCD 顯示目標、搜尋中／已找到狀態、物件框與分割遮罩。

**實作入口：**[整合應用 app.c](../firmware/Src/app.c) 的 `finder_voice_poll`、`finder_select_target`、`nn_thread_fct`、`dp_thread_fct`；[系統架構](architecture.md)。

<a id="step-02"></a>
### 2. 建立正式專案與固定開發環境

- 建立正式雙模型工程，將視覺參考工程、主韌體、語音資料與訓練工具分別放在 `vision/`、`firmware/`、`kws/`。
- 以 ST 手部雙模型範例的開機、攝影機、顯示、FreeRTOS 與 NPU 框架為平台基礎，替換模型並加入本案的資料流程、語音模型、搜尋及顯示邏輯。
- 固定來源提交與工具版本：GCC 14.3.1、ST Edge AI Core 4.0.1、Neural-ART 1.1.3-275、STM32CubeIDE 2.2.0，並記錄推論執行環境版本。
- 將模型產碼、執行期與建置來源的相依關係納入工程管理，讓後續修改能回到對應版本。

**實作入口：**[來源版本](source-provenance.json)、[建置環境](build.md)、[平台初始化 main.c](../firmware/Src/main.c)、[主 Makefile](../firmware/Makefile)。

**原始主機流程：**[建立視覺工程原碼](../tools/development-history/vision_01_prepare_vision.sh)。

<a id="step-03"></a>
### 3. 完成 YOLO 模型匯出、量化與 N6 轉換

- 使用 Python／PyTorch 工具載入原始 YOLOv8n-seg `.pt` 模型，配置 256×256 輸入，匯出 ONNX，再透過 `onnx2tf` 轉成 TensorFlow SavedModel。
- 親自設定並執行逐通道 INT8 量化，配置校正影像、影像縮放及 INT8 輸入輸出，產生 TFLite。
- 在電腦端比較原始、浮點及 INT8 模型，核對輸入輸出形狀、型別、量化尺度、零點及後處理介面。
- 執行 ST Edge AI／Neural-ART 產碼，產生 N6 網路程式、模型介面、權重與執行指令，保存產碼設定及記憶體池配置。
- 完成參考工程的編譯、連結與映像封裝，再將產物接入雙模型韌體，配對執行期與建置流程。
- 保存完整「匯出 → 量化 → 產碼 → 整合」流程的程式、設定、成功日誌與各階段模型指紋。

**實作與紀錄：**[完整視覺轉換流程](../vision/deployment/README.md)、[產碼腳本參考](../vision/deployment/upstream-reference/generate-n6-model_STM32N6570-DK.sh)、[Neural-ART 設定](../vision/deployment/upstream-reference/user_neuralart_STM32N6570-DK.json)、[已保存的 N6 輸入指紋](../sources.txt)、[整合工程流程](engineering-workflow.md)。

**原始主機流程：**[N6 產碼與工程建置](../tools/development-history/vision_03_generate_and_build_vision.sh)；前段 Python 匯出、量化設定、成功日誌及驗證程式由上方完整視覺流程連入。

<a id="step-04"></a>
### 4. 配對模型產碼與推論執行環境

- 將視覺參考工程的執行期（Runtime）由 1200 更新為 1201，將正式手部範例底座由 1100 更新為 1201。
- 同步配對 `Inc`、`Lib`、`Npu` 的標頭、函式庫與 NPU 支援來源，連結 `NetworkRuntime1201_CM55_GCC.a`。
- 保留 FreeRTOS 作業系統抽象層與非同步推論機制；遇到等待事件時交由對應等待介面處理，完成後重設下一輪狀態。
- 對照開發時採用的官方提交，記錄產碼工具、文件基準與建置清單之間的版本差異，以及本案的統一方式。

**實作入口：**[ai.mk](../firmware/mks/ai.mk)、[app.c](../firmware/Src/app.c)、[finder_kws.c](../firmware/Src/finder_kws.c)；[官方版本與本案配對表](toolchain-compatibility.md)。

**原始主機流程：**[參考執行期配對](../tools/development-history/vision_02_match_vision_runtime.py)、[正式執行期配對](../tools/development-history/vision_06_match_main_runtime.py)。

<a id="step-05"></a>
### 5. 將手部模型工程改造成 YOLO 視覺工程

- 移除原掌心偵測、手部關鍵點及相關舊模型的建置項目，納入本案的 YOLO 網路、STAI 介面、權重與執行指令。
- 修改模型與後處理的編譯清單，使正式韌體連結正確來源與推論執行環境。
- 改接模型初始化及輸入輸出緩衝介面，取得各張量指標。
- 核對輸入輸出的數量、尺寸、資料型別、大小與量化資訊，讓擷取、推論與後處理使用一致介面。

**實作入口：**[Makefile](../firmware/Makefile)、[ai.mk](../firmware/mks/ai.mk)、[main.c](../firmware/Src/main.c)、[app.c](../firmware/Src/app.c)；[移植步驟與產物名稱](engineering-workflow.md)。

**原始主機流程：**[六項產物移植](../tools/development-history/vision_05_copy_vision_artifacts.sh)、[模型建置替換](../tools/development-history/vision_07_update_model_build_list.py)。


## 第二階段：視覺搜尋、顯示與記憶體（6–11）

<a id="step-06"></a>
### 6. 配置攝影機輸入與畫面對應

- 配置攝影機影像擷取與處理管線（DCMIPP），分別供顯示與神經網路輸入使用。
- 從 LCD 顯示視野取得中央正方形，作為模型辨識範圍。
- 將該區域縮放成 **256×256 RGB、無號八位元整數（UINT8）**影像。
- 讓模型輸入區域與 LCD 的辨識區域共用同一幾何對應，供後續框與遮罩映射。

**實作入口：**[app_cam.c](../firmware/Src/app_cam.c) 的 `DCMIPP_PipeInitNn`；[app.c](../firmware/Src/app.c) 的 `Display_NetworkOutput`。

<a id="step-07"></a>
### 7. 移植視覺後處理與模型輸出介面

- 納入 ST 實例分割後處理核心及 YOLOv8 轉接層，接上偵測與遮罩原型兩組 INT8 張量。
- 偵測輸出為 `1×116×1344`，涵蓋 4 個框參數、80 個類別與 32 個遮罩係數；遮罩原型為 `1×64×64×32`。
- 配置 **80 類、1,344 個候選位置、32 張 64×64 遮罩原型**，並接入各輸出的量化尺度與零點。
- 整合框解碼、非極大值抑制（NMS）及遮罩重建；偵測信心門檻為 **0.50**、NMS 交併比（IoU）門檻為 **0.40**，最多保留 **10** 個結果。
- 後處理核心保留 ST 來源；本案完成模型介面、參數、建置及搜尋／顯示資料流的適配。

**實作入口：**[YOLOv8 後處理轉接層](../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c)、[ai.mk](../firmware/mks/ai.mk)、[app.c](../firmware/Src/app.c)。

**原始主機流程：**[後處理移植原碼](../tools/development-history/vision_08_import_postprocessing.py)。

<a id="step-08"></a>
### 8. 建立指定物件搜尋與穩定確認

- 將三種命令對應至 COCO 類別：杯子 `41`、瓶子 `39`、手機 `67`。
- 從每輪結果篩選目前目標；同類別有多個物件時，選最高信心框。
- 要求連續 **兩個影格**命中，且框交併比（IoU）至少 **0.30**，才發布已找到（FOUND）。
- 切換目標時清除上一目標的找到狀態及連續命中累積。
- 在加入語音前，先完成正式視覺搜尋功能，保存視覺版板端紀錄。

**實作入口：**[app.c](../firmware/Src/app.c) 的 `finder_select_target`、`box_iou`、`FINDER_CONFIRM_FRAMES` 及 `nn_thread_fct`；[視覺版操作紀錄](evidence/development-history/finder_vision_20261004.log)。

<a id="step-09"></a>
### 9. 顯示物件框、分割遮罩與搜尋狀態

- 將模型座標換回 LCD 中央辨識區域，疊加物件框、遮罩與目前搜尋狀態。
- 推論結果先保存為結果快照，分離後處理工作區與顯示資料的生命週期。
- 顯示工作在互斥鎖內取得自己的繪圖快照，再於鎖外繪圖，縮短共享資料的鎖定時間。
- 使用結果遮罩與繪圖遮罩的分離儲存，避免下一輪後處理覆寫正在顯示的內容。

**實作入口：**[app.c](../firmware/Src/app.c) 的 `result_mask`、`drawing_mask`、`Display_NetworkOutput` 與 `dp_thread_fct`；[資料交接架構](architecture.md)。

<a id="step-10"></a>
### 10. 處理攝影機、中斷與推論間的資料交接

- 以影像緩衝佇列及計數號誌協調攝影機擷取與推論。
- 修正 `bqueue_get_free` 在中斷情境取得空閒緩衝的路徑，使用 `xSemaphoreTakeFromISR`，並以 `portYIELD_FROM_ISR` 處理必要的工作切換。
- 工作情境保留一般號誌介面，依呼叫情境使用正確的 FreeRTOS 操作。
- 取得影像後先處理快取，再複製到模型輸入區；模型輸入完成快取維護後，才將相機緩衝歸還。
- 分開相機下一幀擷取與目前推論輸入的生命週期，避免共享緩衝提早重用。

**實作入口：**[app.c](../firmware/Src/app.c) 的 `bqueue_get_free`、`nn_input_queue` 及 `nn_thread_fct`；[中斷與緩衝修改紀錄](engineering-workflow.md)。

**原始主機流程：**[應用與中斷介面整合原碼](../tools/development-history/vision_12_integrate_vision_application.py)。

<a id="step-11"></a>
### 11. 重新配置視覺工程的記憶體與映像區段

- 將主應用 SRAM 從 **1,535 KiB** 調整為 **1,023 KiB**，範圍為 `0x34000400–0x34100000`，避開視覺模型工作區。
- 將視覺執行指令的 `.flash_blob` 收入 `.flash_section`，放在外部快閃記憶體（Flash）`0x71380000`，保留 **2 MiB**。
- 將顯示與後處理大型緩衝放入外部 PSRAM；後處理輸入區段 `.psram_bss` 收入 `.psram_section (NOLOAD)`。
- 修改連結腳本與建置區段定義，讓程式、工作區、權重及指令各落在預定位置。
- 從同一 ELF 分開輸出主應用與視覺指令，避免跨位址空洞使二進位映像膨脹；後續加入 KWS 時，再從 PSRAM 尾端切出專用區。

**實作入口：**[連結腳本](../firmware/Gcc/STM32N657xx.ld)、[Makefile](../firmware/Makefile)、[視覺記憶體池參考](../vision/deployment/upstream-reference/my_mpools/stm32n6-app2_STM32N6570-DK.mpool)；[完整記憶體配置與映像邊界](memory-deployment.md)。

**原始主機流程：**[裁切與記憶體修改原碼](../tools/development-history/vision_13_configure_camera_and_memory.py)。


## 第三階段：語音資料、模型與量化（12–16）

<a id="step-12"></a>
### 12. 建立正式語音資料收集流程

- 定義 `cup`、`bottle`、`phone`、其他詞語（`unknown`）及安靜底噪（`silence`）五類，使用板上實際麥克風收集裝置端音訊。
- 每段五秒，格式為 **16 kHz、16 位元、單聲道**，共 **80,000** 個樣本。
- 三種命令各錄 **12** 段、其他詞語 **8** 段、安靜 **3** 段，共 **47** 段原始錄音。
- 錄音韌體先將五秒資料收進 RAM，再由主迴圈傳輸；主機透過 GDB RAM 載入工具啟動錄音程式，接收端處理交握、期限、長度、格式與循環冗餘校驗（CRC32）。
- 保存來源及收集工作階段資訊，驗證已完成片段後支援中止再接續。

**實作入口：**[collect_n6.py](../kws/collect_n6.py)、[獨立錄音 main.c](../kws/recording_firmware/FSBL/Src/main.c)、[RAM 啟動工具](../kws/recording_tools/n6_mic_start_and_record.sh)、[WAV 接收工具](../kws/recording_tools/n6_receive_wav.py)。

<a id="step-13"></a>
### 13. 將原始錄音整理為一秒訓練片段

- 以短時能量定位發音區域，限制相鄰單字的切割邊界，避免混入下一個單字。
- 將片段補成一秒，保存原始錄音來源及發音起訖位置。
- 先依五秒原始錄音分成訓練／驗證組，再切短片段，讓同一來源的相近樣本留在同一組。
- 初版得到 **142 段訓練片段與 49 段驗證片段**；47 段錄音與 191 段切片分別記錄。

**實作入口：**[prepare_dataset.py](../kws/prepare_dataset.py) 的 `speech_regions`、`extract_word` 及資料分組流程；[訓練版本歷程](../kws/training_history/README.md)。

<a id="step-14"></a>
### 14. 建立電腦端語音特徵流程

- 對一秒、**16,000 點**音訊去平均值，以 **480 點**週期漢寧窗（Hann window）、**320 點**位移分析。
- 執行 **512 點**快速傅立葉轉換（FFT），計算功率頻譜。
- 通過 **40 個**梅爾濾波器（Mel filters）、自然對數及正交離散餘弦轉換（DCT）。
- 每框保留 **13 個**梅爾頻率倒譜係數（MFCC），形成 **49×13×1** 輸入。
- 用訓練資料計算標準化參數，再將特徵截限；保存窗函數、濾波器、DCT 與標準化係數，供板端共用。

**實作入口：**[定版 train_kws.py](../kws/training_snapshot/train_kws.py) 的 `features` 與係數建立流程；[板端係數表](../firmware/Inc/finder_kws_tables.h)。

<a id="step-15"></a>
### 15. 建立並訓練五分類 KWS 模型

- 設計以 MFCC 為輸入的小型關鍵字辨識（Keyword Spotting，KWS）網路，使用卷積與深度可分離卷積控制運算量及模型大小。
- 納入批次正規化、啟動函數、全域平均池化與隨機失活（Dropout），輸出五類分數。
- 使用類別權重處理資料分布，加入音量、背景噪音與時間平移等資料增強。
- 保存訓練過程、模型、係數與評估；初版浮點及 INT8 的離線驗證皆為 **48/49**。
- 後續依板端現場表現改進資料及訓練，保留初版、現場迭代與最終分組訓練的程式版本。

**實作入口：**[初版訓練程式](../kws/training_history/20261005_baseline/train_kws.py)、[定版網路與增強](../kws/training_snapshot/train_kws.py) 的 `build_model`、`augment`；[訓練歷程](../kws/training_history/README.md)。

<a id="step-16"></a>
### 16. 量化並匯出自行訓練的語音模型

- 將訓練模型匯出為 TensorFlow 儲存模型（SavedModel），使用代表性訓練資料進行量化校正。
- 轉成 **INT8 TFLite**，核對輸入輸出形狀、型別、量化尺度與零點。
- 比較浮點及量化模型的分類結果，保存模型、量化參數與評估報告。
- 同時匯出特徵係數，使語音模型與板端前處理使用同一版本。

**實作入口：**[train_kws_groupcv.py](../kws/training_snapshot/train_kws_groupcv.py) 的 `export_int8`；[訓練快照](../kws/training_snapshot/README.md)、[定版保留音訊報告](evidence/kws-int8-holdout.json)。

## 第四階段：第二模型與即時韌體整合（17–21）

<a id="step-17"></a>
### 17. 為 KWS 建立獨立產碼與 RAM／Flash 配置

- 為 KWS 指定獨立網路名稱與上下文，避免與 YOLO 的產碼符號及介面衝突。
- 在 PSRAM **`0x91FC0000` 保留 256 KiB**，供 KWS 活化值與輸入輸出；在 Flash **`0x70700000` 保留 64 KiB**，供語音權重。
- 執行 ST Edge AI，經工具內部 ONNX 與量化中繼資訊，再由 Neural-ART 編譯；將語音網路、介面與權重接入正式工程。
- 定版配置為 **11 個 NPU 硬體階段與 1 個 CPU Softmax 階段**，權重配置 **11,409 B**、活化值配置 **17,440 B**。
- CPU 執行工具產生的 C 控制流程；此版未啟用執行階段控制器，沒有獨立 KWS 指令包（EC blob）。
- KWS 工作區採產碼絕對位址使用，故連結器在 `KWS_RAM` 顯示 0 B；其實際配置由產碼報告追蹤。

**實作入口：**[kws.mpool](../kws/deployment/kws.mpool)、[kws_neuralart.json](../kws/deployment/kws_neuralart.json)、[kws.mk](../firmware/mks/kws.mk)、[原始產碼命令](evidence/development-history/codegen_20261008/command.json)、[編譯報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)。

**原始主機流程：**[KWS 產碼主機流程](../tools/development-history/generate_groupcv_model.py)。

<a id="step-18"></a>
### 18. 將獨立錄音整合為連續音訊輸入

- 整合多功能數位濾波器（MDF）與通用直接記憶體存取（GPDMA），配置麥克風腳位、分頻、濾波、抽取及周邊存取屬性。
- 保留影像系統既有共用 PLL2，設定麥克風的 IC8 分頻，維持音訊與影像共存。
- 使用循環 DMA，在半滿／全滿回呼處理音訊區塊，略過暖機後寫入 **32,768 點環形緩衝區**。
- 每次取得最新 **16,000 點**，形成一秒視窗；至少累積 **3,200 個新樣本**才再次取窗，名目約 **200 ms**，實際間隔由 DMA 區塊與工作排程共同決定。
- 處理環形跨界；若複製期間延遲到資料可能遭覆寫，捨棄該次快照。

**實作入口：**[finder_mic.c](../firmware/Src/finder_mic.c) 的 `finder_mic_start`、`receive_block`、`finder_mic_take` 及 MDF 回呼；[音訊介面](../firmware/Inc/finder_mic.h)。

<a id="step-19"></a>
### 19. 將 Python 特徵流程移植為 C

- 使用 CMSIS-DSP 實數 FFT，接續功率頻譜、Mel 濾波、對數與 DCT。
- 處理實數 FFT 直流與奈奎斯特頻率的特殊儲存位置，保持與 Python 特徵定義一致。
- 使用訓練匯出的係數進行標準化、截限與 INT8 量化，產生 **637 個 INT8 特徵**。
- 將 FFT、頻譜、功率及特徵工作區設為靜態配置，限制由同一推論工作使用，降低工作堆疊負擔。
- 在編譯與初始化時核對輸入輸出形狀、型別、尺度及零點，及早發現模型與係數版本不一致。

**實作入口：**[finder_kws.c](../firmware/Src/finder_kws.c) 的 `encode_mfcc`、`finder_kws_init`、`finder_kws_classify`；[特徵係數](../firmware/Inc/finder_kws_tables.h)、[DSP 建置清單](../firmware/mks/kws.mk)。

<a id="step-20"></a>
### 20. 處理 CPU、DMA 與 NPU 快取一致性

- DMA 描述節點及音訊緩衝分別對齊 **64／32 位元組**。
- DMA 寫入後維護 CPU 快取，確保處理的是新音訊；以記憶體屏障完成資料交接，再發布環形緩衝的新寫入位置。
- CPU 更新 KWS 輸入前，先回寫並使 NPU 舊快取失效，再使 CPU 舊副本失效。
- CPU 寫完新特徵後回寫快取，供 NPU 讀取；非同步推論等待完成後，準備下一次執行狀態。
- 依輸出實際產生位置處理讀取；定版 KWS 的最後 Softmax 在 CPU 上執行，讀取 CPU 產生的量化輸出。

**實作入口：**[finder_mic.c](../firmware/Src/finder_mic.c) 的快取及環形緩衝處理；[finder_kws.c](../firmware/Src/finder_kws.c) 的 `kws_begin_input_update`、`prepare_input_cache`、`finder_kws_classify`；[資料生命週期](memory-deployment.md)。

<a id="step-21"></a>
### 21. 完成共享 NPU 排程與跨工作狀態管理

- 初始化一次推論執行環境，讓 YOLO 與 KWS 各自保留上下文及輸入輸出。
- 在同一 `nn_thread_fct` 中依序輪詢 KWS、執行 YOLO，共用 NPU；顯示與影像訊號處理（ISP）由另外兩個 FreeRTOS 工作協作。
- 語音透過目標切換介面更新搜尋類別。每次切換更新世代編號，推論完成後再次核對，捨棄屬於舊目標的結果。
- 語音執行期間的收音／分類錯誤停用語音並顯示錯誤，保留視覺運作路徑；此錯誤隔離設計尚無另行故障注入測試。

**實作入口：**[app.c](../firmware/Src/app.c) 的 `nn_thread_fct`、`dp_thread_fct`、`isp_thread_fct`、`finder_select_target`、`finder_voice_poll`；[工作與狀態架構](architecture.md)。

## 第五階段：建置、數值除錯與語音接受（22–25）

<a id="step-22"></a>
### 22. 整合建置並修正啟動與封裝問題

- 將兩模型、後處理、MDF、CMSIS-DSP 及共用推論執行期納入同一建置；FFT 與前處理採一致編譯設定。
- 核對連結區段、容量及分離輸出的映像，對照部署位址。
- 排查寫入驗證成功卻無畫面、無串列輸出的版本，逐位元組比較原始應用程式與封裝內容。
- 確認程式內容一致、有效載荷偏移有差異後，將 **`0x240` 修正為 `0x400`**，重新核對對齊及內容，再完成後續部署。
- 對照官方分割範例文件與 Makefile 的封裝選項差異，保存本案採用的對齊方式及成功紀錄。

**實作與紀錄：**[Makefile](../firmware/Makefile)、[kws.mk](../firmware/mks/kws.mk)、[封裝故障與修正過程](original-history-review.md)、[官方設定與建置指令對照](toolchain-compatibility.md)、[定版建置日誌](evidence/development-history/deployment_20261008/build.log)。

**主機流程：**[封裝內容與偏移檢查](../tools/development-history/inspect_boot_payload.py)、[對齊與寫入流程](../tools/development-history/realign_and_flash_application.sh)、[後續寫入重試](../tools/development-history/retry_aligned_application_flash.sh)。

<a id="step-23"></a>
### 23. 建立電腦與板端的分層數值比對

- 第一層直接輸入固定 INT8 特徵，檢查模型部署；第二層輸入相同 PCM，檢查 C 前處理加推論。
- 第三層回傳即時音訊、實際特徵及模型輸出，在電腦重新計算，對照同一視窗。
- 五類各一個固定樣本在 INPUT／PCM 兩路的分類均與電腦一致；PCM 路徑每段 **637 個特徵逐項一致**。
- 該固定組兩路的輸出最大差異皆不超過 **1 個量化整數單位**，其中四類為 0、silence 為 1。
- 比較結果用於區分模型介面、前處理與資料交接問題；分類表現另依對應模型的驗證集合評估。

**實作與紀錄：**[finder_kws.c](../firmware/Src/finder_kws.c) 的 `finder_kws_compare`、`finder_kws_live_capture`；[比較開關](../firmware/Inc/finder_kws_compare.h)、[固定參考資料](../firmware/Inc/finder_kws_compare_data.h)、[電腦參考 JSON](evidence/development-history/fixed_reference_20261007.json)、[原始比較結果](original-history-review.md)。

**主機流程：**[匯出固定參考](../tools/development-history/export_fixed_reference.py)、[安裝比較版本](../tools/development-history/install_fixed_comparison.py)、[比較版建置與部署](../tools/development-history/build_flash_fixed_comparison.py)。

**原始主機流程：**[即時接收與電腦重算](../tools/development-history/compare_live_windows.py)。

<a id="step-24"></a>
### 24. 利用即時資料定位現場誤判與漏接

- 保存同一視窗的 PCM、637 個特徵、五類輸出及峰值，以分段資料與 CRC32 回傳。
- 比較四個即時視窗時，INT8 特徵皆一致；silence、cup、bottle、phone 的輸出最大整數差異依序為 **0、0、3、1**。
- 安靜案例在板端、電腦直接特徵與完整前處理三路皆判成手機；瓶子案例雖排名第一，分數仍不足接受門檻。
- 加入最高分、與第二名分差、連續命中及削波統計，將相同數值仍誤判的案例定位到資料與模型表現。
- 先補四段現場音訊，訓練片段由 142 增至 146、驗證仍為 49；離線結果維持 48/49，但後續一輪六次口令只接受兩次，因而繼續擴充現場資料及訓練流程。

**實作與紀錄：**[finder_kws.c](../firmware/Src/finder_kws.c) 的 `finder_kws_live_capture`、`live_send`；[app.c](../firmware/Src/app.c) 的語音診斷；[即時比較報告](evidence/development-history/live_comparison_20261007.json)、[現場迭代歷程](original-history-review.md)、[現場訓練版本](../kws/train_kws_live_v3.py)。

**主機流程：**[安裝即時比較](../tools/development-history/install_live_comparison.py)、[比較版建置與部署](../tools/development-history/build_flash_live_comparison.py)、[接收視窗並在電腦重算](../tools/development-history/compare_live_windows.py)、[記錄語音診斷](../tools/development-history/record_voice_diagnostics.py)。

<a id="step-25"></a>
### 25. 建立語音命令接受狀態機

- 音訊峰值至少 **2,500**、最高類別分數至少 **90%**，且領先第二名至少 **25 個百分點**。
- 要求連續 **兩個視窗**符合條件，兩次命令接受間隔至少 **1,200 ms**。
- 接受後解除啟用，等待 **兩個安靜視窗**才重新啟用，避免同一持續發音反覆接受。
- 顯示最後接受的命令，降低逐窗候選分數變動造成的畫面跳動。
- 定版沿用這些接受條件，透過後續資料擴充、模型訓練及同步部署改善實際辨識。

**實作入口：**[app.c](../firmware/Src/app.c) 的 `finder_voice_poll`、`hits`、`quiet_windows`、`armed` 與語音門檻設定；[定版語音紀錄](evidence/development-history/voice_groupcv_20261008.log)。

## 第六階段：資料迭代、定版訓練與部署（26–30）

<a id="step-26"></a>
### 26. 擴充現場資料與重整開發／保留集合

- 從正式板端收集 **48 段現場音訊**，其中 **32 段**用於開發、**16 段**保留評估。
- 將原 142 段訓練、49 段驗證、先前四段現場及新增 32 段，合為 **227 段開發資料**。
- 保存每段的標籤、用途、來源及 PCM 雜湊，增加板上實際語音與底噪的覆蓋。
- 依發音能量與邊界限制時間平移，避免資料增強截掉單字。
- 原 49 段驗證已納入開發池，定版另以保留的 16 段音訊評估。

**實作與紀錄：**[現場收集計畫](../kws/live_collection_plan.json)、[48 段收集清單](evidence/development-history/live_dataset_manifest_20261008.json)、[訓練特徵與增強](../kws/training_snapshot/train_kws.py)、[開發資料載入](../kws/training_snapshot/train_kws_groupcv.py)。

**主機流程：**[準備收集版本](../tools/development-history/prepare_live_collection.py)、[建置及部署收集版本](../tools/development-history/build_flash_live_collection.py)、[收集現場資料](../tools/development-history/collect_live_dataset.py)、[核對資料集](../tools/development-history/check_live_dataset.py)。

<a id="step-27"></a>
### 27. 實作防洩漏的分組五折驗證與最終訓練

- 按原始錄音分組，用 PCM 雜湊識別相同內容並合併來源組別，使相關片段留在同一折。
- 檢查標籤矛盾、組別交疊、各折類別覆蓋、每筆資料恰好驗證一次，以及開發／保留資料重複。
- 每折只用該折訓練資料計算標準化、選取背景噪音及建立量化校正資料。
- 完成分層分組五折驗證，INT8 合計 **224/227，98.68%**。
- 五折最佳輪數為 **82、28、66、9、79**，取中位數 **66 輪**，使用全部 227 段開發資料訓練最終模型。

**實作與紀錄：**[train_kws_groupcv.py](../kws/training_snapshot/train_kws_groupcv.py) 的 `load_development`、`make_splits`、`make_training`、`fit_model`、`export_int8`；[五折報告](evidence/kws-groupcv.json)、[訓練歷程](../kws/training_history/README.md)。

<a id="step-28"></a>
### 28. 評估定版模型並同步板端相依產物

- 在保留的 **16 段**音訊上分別評估浮點及 INT8，兩者均為 **15/16，93.75%**。
- 保存唯一分類錯誤的杯子樣本與分數；它被判為手機，分數約 **60.9%**，低於 **90%** 的命令分數門檻。
- 對定版 INT8 模型重新執行 N6 產碼，同步模型程式、權重、前處理係數、尺度與零點。
- 輸入零點由 **8 更新為 7**；關閉開發用即時收集與比較開關，建置定版韌體。
- 保存模型雜湊與產碼設定，將離線評估、模型產物與板端版本連在一起。
- 當時產碼完成後，遞迴搜尋把工具工作目錄的同名檔一併算入，導致產物檢查停止；後續限定正式輸出重新核對，再完成安裝與建置。

**實作與紀錄：**[保留音訊報告](evidence/kws-int8-holdout.json)、[定版產碼日誌](evidence/development-history/codegen_20261008/codegen.log)、[模型 SHA-256](evidence/development-history/codegen_20261008/model_sha256.txt)、[前處理係數](../firmware/Inc/finder_kws_tables.h)、[開發比較設定](../firmware/Inc/finder_kws_compare.h)。

**主機流程：**[定版產碼與原檢查](../tools/development-history/generate_groupcv_model.py)、[正式輸出核對](../tools/development-history/inspect_groupcv_codegen.py)、[同步安裝與建置](../tools/development-history/install_build_groupcv.py)。

<a id="step-29"></a>
### 29. 整理五份映像並部署定版更新

- 將交付內容分為第一階段開機載入程式（FSBL）、主應用、視覺權重、KWS 權重及視覺執行指令，逐項記錄位址、容量與雜湊。
- FSBL 依 HEX 內含位址寫入；主應用儲存在 **`0x70100000`**、視覺權重在 **`0x70380000`**、KWS 權重在 **`0x70700000`**、視覺指令在 **`0x71380000`**。
- 核對儲存位址與執行位址的分工：主應用映像位於 Flash，連結執行位置在內部 SRAM。
- 定版更新實際寫入並驗證主應用與 KWS 權重，其餘映像沿用既有配置；保留兩份寫入成功紀錄。
- 核對視覺權重實際長度及 KWS 起點間隔，讓產碼配置、連結結果與部署內容相互對應。

**實作與紀錄：**[映像清單](evidence/development-history/deployment_20261008/flash_manifest.json)、[寫入驗證摘要](evidence/development-history/deployment_20261008/flash_verified.json)、[應用寫入紀錄](evidence/development-history/deployment_20261008/flash_finder_signed.bin.log)、[KWS 權重寫入紀錄](evidence/development-history/deployment_20261008/flash_kws_weights.bin.log)、[位址與邊界](memory-deployment.md)。

**主機流程：**[定版映像檢查、寫入與驗證](../tools/development-history/flash_groupcv.py)。

<a id="step-30"></a>
### 30. 保存定版板端操作與不同版本結果

- 杯子、瓶子、手機各操作兩次，**六次語音命令均正確接受**，接受後目標與命令一致。
- 保存其他詞語及兩段安靜未接受命令的紀錄；安靜期間的結果對應音量閘控，與模型單窗分類評估分開記錄。
- 同一輪定版日誌的視覺訊息為 `found=0`；這輪統計語音接受及目標對應。較早視覺版本的 CUP／PHONE `found=1` 紀錄另列。
- 依模型版本、測試方法及日誌區分離線分類、命令接受、視覺找到物件與影片展示。

**紀錄入口：**[定版語音操作](evidence/development-history/voice_groupcv_20261008.log)、[逐列觀察摘要](evidence/development-history/observations.json)、[較早視覺日誌](evidence/development-history/finder_vision_20261004.log)、[結果與版本對照](results.md)。

**主機流程：**[定版板端觀察與日誌保存](../tools/development-history/record_voice_groupcv.py)。

## 第七階段：工程保存與實機展示（31–32）

<a id="step-31"></a>
### 31. 整理 IDE、工程保存與 GitHub 公開內容

- 同步整合開發環境（IDE）的來源及標頭瀏覽入口，核對連結與實際工程；保留預覽、備份、雜湊競態檢查及原子替換。
- 建置入口依專案位置解析路徑，支援 `GCC_PATH` 指定編譯器，核對 **GCC 14.3.1**。
- 保存主應用、收音韌體與主機工具、資料整理、訓練版本及定版快照、模型配置、來源版本、模型雜湊及部署紀錄。
- 提供中英文首頁、完整步驟、架構、模型流程、程式導讀、記憶體、建置及成果說明，從技術敘述直接連到對應來源。
- 完成 Git 保存與 GitHub 公開，保留元件版權及授權；模型權重、原始錄音、模型產碼及預建映像的材料範圍另列於公開與建置說明。

**實作入口：**[IDE 同步程式](../tools/ide/sync_cubeide_sources.py)、[IDE 使用方式](../tools/ide/README.md)、[建置入口](../firmware/STM32CubeIDE/STM32N6570-DK/cubeide_make.sh)、[公開材料盤點](publication-review.md)、[建置依賴](build.md)、[第三方來源](../THIRD_PARTY_NOTICES.md)。

<a id="step-32"></a>
### 32. 完成影片展示並記錄獨立運作狀態

- 實機影片已完成並放在專案首頁醒目位置：[觀看雙模型語音找物展示](https://youtu.be/m7wET9g5u6k)。
- 影片作為操作展示入口，與程式、模型評估、板端日誌及部署紀錄一同呈現作品。
- 獨立供電與斷電重上屬於另外的啟動／操作驗證；目前尚無已核對的完成紀錄，保留其實測狀態。

**閱讀入口：**[首頁實機展示](../README.md)、[影片](https://youtu.be/m7wET9g5u6k)、[展示及測試範圍](results.md)、[開機映像配置](memory-deployment.md)。

---

詳細函式說明見[程式導讀](code-tour.md)；工作與材料對照見[實作索引](development-coverage.md)；數值與版本見[結果](results.md)。
