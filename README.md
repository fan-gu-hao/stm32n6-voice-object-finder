# STM32N6 雙模型語音找物系統

在 STM32N6570-DK 上整合自行訓練的關鍵字辨識（Keyword Spotting，KWS）與 YOLOv8 實例分割。使用 cup、bottle、phone 語音命令選擇搜尋目標，液晶螢幕（LCD）顯示搜尋狀態、物件框與分割遮罩。

本作品涵蓋模型部署、音訊驅動與資料蒐集、特徵前處理、模型訓練與 INT8 量化、電腦／板端比對、快取與記憶體配置，以及 FreeRTOS 多工作整合。視覺持續執行，語音改變搜尋目標；兩個模型在同一推論工作中依序使用神經網路處理器（NPU），顯示與影像訊號處理（ISP）由另外的工作協作。

## 完整開發流程

**[工程流程、跨階段延續與實作證據](docs/engineering-workflow.md)** 將各階段的程式、設定、修補與結果串在一起：

- 前期視覺作品完成原始模型 → ONNX → onnx2tf／SavedModel → ST 逐通道 INT8，再進行 N6 編譯與部署；已有三模型比較、模型庫輸出對應及部署參數修補。對應[視覺專案](https://github.com/fan-gu-hao/stm32n6-instance-segmentation)的程式與日誌。
- 從板上錄音、RAM 載入與 UART 交握／CRC32 檢查，建立自行收集的五分類語音資料。
- 實作 MFCC、深度可分離卷積 KWS、資料增強、原始錄音分組、PCM 雜湊排重、五折驗證與保留音訊評估。
- 將 KWS 量化與部署至 N6，保留固定輸入／PCM 分層比對及即時 PCM、特徵、輸出回傳的除錯程式。
- 整合 MDF／GPDMA、CPU／DMA／NPU 快取一致性、雙模型排程、搜尋狀態、顯示與獨立記憶體區域。
- 保存建置與模型配置、定版訓練快照、評估報告、來源紀錄及五映像交付流程。

前期自行量化與後處理適配工作，以及本版實際選用的模型來源，都在工程導覽中列明。

## 建議閱讀的程式

| 入口 | 工程重點 |
| --- | --- |
| [獨立錄音韌體](kws/recording_firmware/README.md)／[主機工具](kws/recording_tools/README.md) | DMA 回呼、錄音狀態、逾時、CRC32；RAM 載入、串列交握與 WAV 保存 |
| [資料整理](kws/prepare_dataset.py) | 短時能量切段、相鄰發音邊界、按原始錄音分組 |
| [定版 KWS 訓練](kws/training_snapshot/train_kws.py) | MFCC、資料增強與深度可分離卷積網路 |
| [定版分組交叉驗證](kws/training_snapshot/train_kws_groupcv.py) | PCM 雜湊排重、分組切分、每折標準化、INT8 匯出與評估 |
| [訓練版本演進](kws/training_history/README.md) | 初版訓練原檔、現場資料改進與分組定版的實作差異 |
| [收音模組](firmware/Src/finder_mic.c) | MDF1、GPDMA 循環鏈結、環形緩衝、滑動視窗、DMA 快取一致性 |
| [板端 KWS 與對照工具](firmware/Src/finder_kws.c) | C MFCC、量化介面檢查、CPU／NPU 快取、固定輸入與即時資料比對 |
| [整合應用](firmware/Src/app.c) | 三個工作、緩衝與號誌、命令狀態機、目標世代與連續幀判定 |
| [記憶體配置](firmware/Gcc/STM32N657xx.ld)／[KWS 記憶體池](kws/deployment/kws.mpool) | 應用、模型指令、顯示與模型暫存區的配置 |
| [建置入口](firmware/Makefile)／[KWS 建置清單](firmware/mks/kws.mk) | 雙模型與執行環境整合、CMSIS-DSP 設定、映像分段輸出 |
| [IDE 來源同步工具](tools/ide/README.md) | 來源連結檢查、預覽、備份、雜湊競態檢查與原子替換 |

函式層級的閱讀順序見 [程式導讀](docs/code-tour.md)。

[開發歷程原始證據](docs/evidence/development-history/README.md)另附早期板端比對、現場資料清單、定版產碼與寫入紀錄及實際語音／視覺日誌。KWS 的 ST 編譯階段也保存了工具內部 ONNX 與量化資訊的轉換紀錄；與前期 YOLO 主動匯出 ONNX 的流程分別說明。

## 系統行為

- 音訊以名目 16 kHz 收音，每個視窗 16,000 點，約每 200 ms 更新。
- 梅爾頻率倒譜係數（MFCC）量化成 49×13×1 INT8，模型輸出 cup、bottle、phone、unknown、silence。
- 命令接受使用音量、分數、分差、連續視窗、最短間隔與安靜後重新啟用條件。
- 視覺輸入為 256×256 RGB UINT8，整合官方實例分割後處理並篩選目標類別。
- 連續兩幀物件框交併比（IoU）符合條件後顯示已找到（FOUND）；切換目標時捨棄舊目標的過期結果。
- USER1 按鍵也可切換搜尋目標；UART 保存語音、搜尋狀態與時間資訊。

## 已有結果

| 項目 | 結果 | 適用範圍 |
| --- | --- | --- |
| 五折開發驗證 | 224/227，98.68% | 用於開發與選輪，非獨立最終測試 |
| 保留音訊 INT8 評估 | 15/16，93.75% | 小樣本、單窗離線評估 |
| 既有板上語音紀錄 | 六次指定命令正確接受 | 同輪視覺紀錄均為 found=0 |

早期固定輸入／PCM 對照、即時音訊回傳與現場資料迭代的歷程見 [結果說明](docs/results.md)。展示影片待補；本作品的獨立供電與冷啟動未列為已驗證項目。前期視覺專案的 A1～A5 驗證另有完整證據與適用版本。

## 文件與來源

- [完整工程流程](docs/engineering-workflow.md)
- [程式導讀與修改重點](docs/code-tour.md)
- [系統架構](docs/architecture.md)
- [建置與外部依賴](docs/build.md)
- [公開內容與本機證據盤點](docs/publication-review.md)
- [第三方來源與公開範圍](THIRD_PARTY_NOTICES.md)

公開版本保存應用與訓練原始碼、配置及工程證據。模型權重、模型產碼與預建燒錄映像未包含於本庫，完整建置須具備對應依賴。上游元件保留來源聲明，專案完成的轉換、修改、整合與驗證工作在導覽中逐項呈現。
