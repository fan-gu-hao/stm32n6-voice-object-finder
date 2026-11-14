# STM32N6 雙模型語音找物系統

[繁體中文](README.md) | [English](README.en.md)

**嵌入式 AI、音訊周邊整合、模型量化與部署、FreeRTOS 多工作協作。**

在 STM32N6570-DK 上，以自行建立資料並訓練的關鍵字辨識（Keyword Spotting，KWS）選擇搜尋目標，再由 YOLOv8 實例分割持續辨識攝影機畫面。說出 `cup`、`bottle` 或 `phone`，液晶螢幕（LCD）顯示目標、搜尋狀態、物件框與分割遮罩；USER1 按鍵提供手動切換。

開發工作從前期視覺模型的匯出、量化與模型庫修補，延伸到板上收音、資料製作、客製 KWS、Python／C 數值對照，再完成兩個模型共用神經網路處理器（NPU）的即時系統。本文直接呈現各階段實作，程式與原始紀錄可由各節連結查閱。

**已保存結果：**五折開發驗證 **98.68%（224/227）**、16 段保留音訊 INT8 評估 **93.75%（15/16）**；早期四例板端／電腦比對的 INT8 特徵差異皆為 **0**。[結果與版本範圍](docs/results.md)

## 核心實作一覽

| 工程面向 | 實際完成的工作 | 原始碼與證據 |
| --- | --- | --- |
| **模型轉換與量化** | 原始 YOLO 權重經 ONNX、SavedModel 到 ST 逐通道 INT8；比較原始、浮點與量化模型，核對輸入輸出介面 | [前期視覺模型流程](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md) |
| **模型庫與部署修補** | 修正偵測／遮罩輸出對應、檢查產生標頭、傳入本機 Neural-ART 配置、修正映像對齊 | [模型庫修補與部署程式](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| **音訊周邊與 DMA** | MDF 時脈、腳位與存取權限；循環 DMA、快取維護、環形緩衝及一秒滑動視窗 | [finder_mic.c](firmware/Src/finder_mic.c) |
| **資料蒐集工具鏈** | 獨立錄音韌體、RAM 載入與向量檢查、串列交握、CRC32、WAV 保存、分類收集與能量切段 | [錄音韌體](kws/recording_firmware/README.md)、[主機工具](kws/recording_tools/README.md)、[資料整理](kws/prepare_dataset.py) |
| **客製模型與資料品質** | MFCC、深度可分離卷積、四版訓練演進、資料增強、來源組別合併、防洩漏、五折驗證與 INT8 匯出 | [訓練歷程](kws/training_history/README.md)、[分組訓練](kws/training_snapshot/train_kws_groupcv.py) |
| **數值移植與分層除錯** | C 特徵前處理、量化參數契約、CPU／NPU 快取順序、固定輸入／PCM 比較與即時資料回傳 | [finder_kws.c](firmware/Src/finder_kws.c)、[比較紀錄](docs/evidence/development-history/README.md) |
| **多工作與狀態一致性** | 三個工作協作、兩模型依序共用 NPU、目標世代、遮罩快照、語音接受狀態機與按鍵備援 | [app.c](firmware/Src/app.c)、[相機適配](firmware/Src/app_cam.c) |
| **記憶體、建置與交付** | 分區配置、模型指令獨立輸出、DSP 編譯設定一致性、IDE 來源同步、版本與映像雜湊追溯 | [連結腳本](firmware/Gcc/STM32N657xx.ld)、[建置清單](firmware/mks/kws.mk)、[IDE 工具](tools/ide/README.md) |

## 模型轉換、量化與後處理適配

### 視覺模型的完整部署路線

前期[視覺實例分割作品](https://github.com/fan-gu-hao/stm32n6-instance-segmentation)完成：

**上游預訓練權重（PyTorch）→ ONNX → onnx2tf／SavedModel → ST 逐通道 INT8 TFLite → ST Edge AI／Neural-ART → N6。**

- 先確認原始模型的圖片與攝影機輸出，再比較原始模型、浮點 TFLite 與 ST INT8，保存模型雜湊、參數、日誌與結果圖。
- 修改模型庫的設定產生器，依張量形狀辨識 `1×116×1344` 偵測輸出與 `1×64×64×32` 遮罩原型；核對 80 類、1344 候選、32 個遮罩係數、型別與量化參數。
- 修補本機產碼參數，傳入 Neural-ART 配置、記憶體池及輸入輸出格式；對齊模型產碼與執行期函式庫，修正映像標頭與對齊流程。
- 在本雙模型版接入 ST 後處理，完成目標類別篩選、連續幀確認、框與遮罩的畫面座標轉換。

上述自行量化與工具修補屬於前期作品的工程成果；本版視覺實際採用 [sources.txt](sources.txt) 記錄的 ST 模型，兩者版本分開追溯。後處理的 NMS 與遮罩重建核心沿用 ST，本作品的修改重點是輸出適配、部署及應用整合。

### 自行訓練的語音模型

**板上錄音 → 切段與分組 → MFCC → Keras 模型訓練 → INT8 TFLite → ST 內部 ONNX／量化資訊 → Neural-ART → N6。**

KWS 編譯保存獨立網路名稱、記憶體池及量化介面。產碼報告記錄 **11 個硬體執行階段與 1 個 CPU Softmax 階段**；權重配置 **11,409 位元組**、活化值配置 **17,440 位元組**。這些是 KWS 編譯配置統計。[產碼命令與原始報告](kws/deployment/README.md)

## 從獨立錄音到連續音訊輸入

獨立收音階段將官方 MDF 範例改成「先在 RAM 收滿五秒，再傳回電腦」：DMA 半滿／全滿回呼略過暖機區塊並複製樣本，主迴圈處理逾時、錯誤、錄音長度及 CRC32。實際輸入由數位麥克風經多功能數位濾波器（MDF）取得。

主機工具核對映像大小、初始堆疊與入口向量，透過 RAM 載入和中斷點確認啟動；接收端處理串列獨占、非阻塞讀取、期限、交握、完整長度、結尾與 CRC32，確認完整後保存 WAV。分類收集工具支援中止後接續，並保留來源與工作階段資訊。

整合到雙模型後，收音改為持續運作：

- **共享時脈與權限**：保留既有 PLL2，只設定麥克風的 IC8 分頻；配置 PE2／PE8、MDF 與 DMA 存取屬性。
- **DMA 與快取**：循環鏈結描述節點與樣本緩衝分別對齊 64／32 位元組；回呼完成快取處理後，用記憶體屏障發布環形緩衝位置。
- **滑動視窗一致性**：名目 16 kHz、每窗 16,000 點、約每 200 ms 更新；處理環形跨界，若複製過程延遲到資料可能被覆寫，就捨棄該次快照。

程式：[獨立錄音來源與上游差異](kws/recording_firmware/README.md) · [RAM 啟動與接收工具](kws/recording_tools/README.md) · [連續收音模組](firmware/Src/finder_mic.c)

## 資料工程與 KWS 訓練演進

建立 `cup`、`bottle`、`phone`、`unknown`、`silence` 五分類資料。以短時能量切出發音、限制相鄰單字邊界並補成一秒；先依原始錄音分組，再切片，讓同一來源的相近片段保持在同一分組。

訓練從初版、現場資料第二／第三版，演進到分組交叉驗證定版：

- **特徵與網路**：49×13×1 MFCC 輸入、深度可分離卷積網路、類別權重與 INT8 匯出。
- **現場資料改進**：補充板上語音及底噪；加入增益、噪音和時間平移，依發音邊界限制平移幅度，避免增強時截掉單字。
- **資料洩漏防護**：以 PCM 雜湊識別相同內容並合併來源組別，拒絕標籤矛盾及開發／保留資料重複；每折的標準化與背景噪音只來自訓練組。
- **可追溯評估**：檢查每折類別覆蓋與組別不交疊，五折選擇訓練輪數後重訓；現場收集清單另保存 48 段音訊的用途與雜湊，其中 32 段供訓練、16 段保留。

程式：[切段與分組](kws/prepare_dataset.py) · [MFCC 與模型](kws/training_snapshot/train_kws.py) · [分組驗證與量化](kws/training_snapshot/train_kws_groupcv.py) · [版本演進](kws/training_history/README.md)

## Python／C 數值對照與問題定位

板端用 CMSIS-DSP 浮點 FFT，接續 Mel 濾波、對數及 DCT，再標準化、截限並量化成 INT8。移植時處理實數 FFT 的直流／奈奎斯特儲存位置，並在編譯及初始化階段檢查形狀、型別、尺度與零點。

除錯分三層：**固定 INT8 輸入測模型 → 同一 PCM 測完整 C 前處理 → 回傳即時 PCM、特徵與輸出，在電腦重算。** 早期四個即時視窗的板端與電腦 INT8 特徵完全一致，輸出最大整數差異依序為 0、0、3、1。

其中一個安靜視窗在板端、電腦直接特徵輸入及電腦完整前處理三路都被判為 `phone`。這個比對把當次問題定位到模型／資料表現，支持後續現場資料迭代；失敗案例與後來定版結果分開保存。

程式：[前處理、推論與比較工具](firmware/Src/finder_kws.c) · [前處理係數](firmware/Inc/finder_kws_tables.h) · [原始比較與結果](docs/results.md)

## FreeRTOS 多工作與共享資源整合

在 Cortex-M55 上，推論、顯示與影像訊號處理（ISP）三個工作協作。**視覺持續執行；語音切換搜尋目標。KWS 與 YOLO 在同一推論工作中依序使用 NPU。**

| 工程問題 | 程式中的處理方式 |
| --- | --- |
| 相機擷取與推論共用資料 | 將相機緩衝複製至模型輸入、完成快取維護後才歸還，分開擷取與推論的資料生命週期 |
| CPU／DMA／NPU 看見不同資料 | DMA 接收後處理 CPU 快取；CPU 寫新模型輸入前處理 NPU 舊快取，寫入完成再清理 CPU 快取，搭配對齊與記憶體屏障 |
| 推論途中切換目標 | 用目標世代編號核對結果，捨棄屬於舊目標的過期推論，重新累積連續命中 |
| 後處理覆寫正在顯示的遮罩 | 模型輸出先複製為結果快照，顯示工作在互斥鎖內再取得繪圖快照，於鎖外繪製 |
| 相機裁切與 LCD 位置不一致 | 從顯示視野取中央正方形作為 256×256 模型輸入，再將框與遮罩映射回 LCD 對應區域 |
| 語音重複接受或不穩定 | 綜合音量、分數、分差、連續兩窗、最短間隔及安靜後重新啟用條件 |
| 物件框短暫跳動 | 篩選指定類別的最高信心結果，連續兩幀且框交併比（IoU）至少 0.30 才顯示找到（FOUND） |
| 語音通路執行期間回傳錯誤 | 停用語音並顯示錯誤，保留視覺及 USER1 手動切換路徑；按鍵具上升緣與 200 ms 去彈跳處理 |

系統沿用 ST 手部雙模型範例的啟動、靜態工作與相機框架，再改接音訊／視覺模型與上述資料、狀態交接。語音錯誤隔離是程式設計，未另做故障注入驗證，亦不涵蓋初始化斷言失敗。

程式：[推論、顯示與狀態機](firmware/Src/app.c) · [相機裁切](firmware/Src/app_cam.c) · [CPU／NPU 快取順序](firmware/Src/finder_kws.c)

## 記憶體、建置與交付

| 配置 | 位置與用途 |
| --- | --- |
| KWS 活化值保留區 | `0x91FC0000`，256 KiB，與應用／顯示 PSRAM 分開 |
| KWS 權重保留區 | `0x70700000`，64 KiB |
| 視覺指令區 | `0x71380000`，2 MiB，從 ELF 的 `.flash_section` 獨立輸出 |

以上為保留容量；模型實際配置量由產碼報告另行核對。建置清單整合 MDF、CMSIS-DSP、兩個模型與執行期，讓 FFT 與前處理物件採一致的編譯設定。交付分為 **FSBL、應用、視覺權重、KWS 權重、視覺指令** 五份映像，保存位址、模型版本、來源與雜湊，以及既有寫入驗證紀錄。

另完成 IDE 來源同步工具：檢查既有連結、預覽修改、備份、雜湊競態檢查與原子替換；建置入口支援 `GCC_PATH` 並核對 GCC 14.3.1，讓 IDE 瀏覽來源與實際 Makefile 建置清單各司其職。

程式：[連結腳本](firmware/Gcc/STM32N657xx.ld) · [Makefile](firmware/Makefile) · [KWS 建置](firmware/mks/kws.mk) · [IDE 同步](tools/ide/README.md) · [部署證據](docs/evidence/development-history/README.md)

## 已有結果與適用範圍

| 項目 | 結果 | 證據與解讀 |
| --- | --- | --- |
| 五折 KWS 開發驗證 | **224/227，98.68%** | [五折報告](docs/evidence/kws-groupcv.json)；用於開發與選輪 |
| 保留音訊 INT8 評估 | **15/16，93.75%** | [保留報告](docs/evidence/kws-int8-holdout.json)；16 段單窗離線評估，一例 cup 判為 phone |
| 早期即時部署一致性 | **四例 INT8 輸入特徵差異皆為 0** | [比較紀錄](docs/evidence/development-history/live_comparison_20261007.json)；用於定位數值與移植問題 |
| 定版板上語音紀錄 | **cup、bottle、phone 各兩次正確接受** | [操作日誌](docs/evidence/development-history/voice_groupcv_20261008.log)；同輪視覺均為 `found=0`，此列統計語音接受 |
| 較早版本視覺紀錄 | CUP、PHONE 有 `found=1` | [視覺日誌](docs/evidence/development-history/finder_vision_20261004.log)；與定版語音紀錄分屬不同版本 |

展示影片待補；本雙模型版本的獨立供電與冷啟動尚未列為實測通過。[完整結果與版本對照](docs/results.md)

## 前期視覺作品的驗證與歷史實驗

雙模型整合前，已在[視覺實例分割作品](https://github.com/fan-gu-hao/stm32n6-instance-segmentation)完成以下工程驗證並公開材料：

| 階段 | 實際工作 |
| --- | --- |
| A1：來源與重建 | 固定上游版本、保存修改與二進位相依、來源隔離還原、既有環境乾淨重建及燒錄讀回 |
| A2：正確性 | 固定像素、原始張量數值比較、框／遮罩共同後處理、後端差異診斷與 50 張回歸 |
| A3：效能 | 管線分段計時、暖機後重複推論、逐區塊分析、串列與量測日誌成本 |
| A4：記憶體 | 固定其他條件調整記憶體池，核對實體配置量、兩版計時及 50 張輸出逐位元組一致性 |
| A5：可靠性 | 冷啟動、區域事件、長測異常分析與重新量測、擷取通知逾時注入、正式韌體還原 |
| UART 中斷試驗 | 環形佇列、完整列提交、重要訊息預留、HAL 相依修復、兩版安裝工具、部署與還原 |

這些是前期作品的測試與實驗結果。UART 中斷版本及 A4 實驗配置保留歷史，正式視覺版本的採用狀態各自記錄。[完整工作與原始證據索引](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md)

## 文件、建置與來源

- [從起步到定版的工作與證據對照](docs/development-coverage.md)：跨階段成果及尚待取得的早期歷史材料。
- [程式導讀](docs/code-tour.md)與[系統架構](docs/architecture.md)：函式、執行流程與配置。
- [工程流程](docs/engineering-workflow.md)與[原始證據](docs/evidence/development-history/README.md)：模型、資料、部署及實測紀錄。
- [建置與外部依賴](docs/build.md)：GCC 14.3.1、ST Edge AI 4.0.1、Neural-ART 1.1.3-275、CubeIDE 2.2.0 及相依項目。
- [公開材料盤點](docs/publication-review.md)與[第三方來源](THIRD_PARTY_NOTICES.md)：保存範圍與授權。

公開儲存庫提供應用與訓練原始碼、配置、修補及工程證據。模型權重、模型產碼、原始錄音與預建映像未隨庫提供；完整建置須具備對應依賴。HAL、BSP、CMSIS-DSP、FreeRTOS、ST 推論執行期與視覺後處理保留上游來源；本作品的資料、訓練、適配、整合、排錯與驗證工作列於上文。
