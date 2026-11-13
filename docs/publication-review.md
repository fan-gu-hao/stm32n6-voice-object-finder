# 工程成果與公開材料盤點

後續重審新增[從起步到定版的工作與證據對照](development-coverage.md)。下列 67 項是已提供材料的處理清單，並非整個 STM32N6 專案所有對話與檔案的完整母清單；早期環境、course13 及臨時終端程式仍有明列的歷史缺口。

整理日期：2026-11-13。本次以使用者提供的 67 項原始碼／證據報告，接續核對已公開的雙模型版本 988aeb31f35e358c7c75bc898e52a201da4b9298 與視覺版本 c044d7d4230eb2438340255e51df5c88162a3fda。原始專案與定版韌體保持原狀。

## 各階段的公開入口

| 工程階段 | 保存的實作與證據 | 公開入口 |
| --- | --- | --- |
| 前期模型與工具環境 | 原始模型、ONNX、onnx2tf／SavedModel、ST INT8、工具版本與成功日誌 | [視覺完整工作索引](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/WORK_IMPLEMENTATION_INDEX.md) |
| 模型庫後處理適配 | 偵測／遮罩輸出識別、量化介面與產生標頭修補；本機 Neural-ART 參數及映像對齊修補 | [視覺工程導覽](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| 視覺驗證與實驗 | A1 來源、A2 數值與框／遮罩、A3 效能、A4 記憶體、A5 可靠性 | [視覺專案](https://github.com/fan-gu-hao/stm32n6-instance-segmentation) |
| 串列中斷歷史試驗 | 佇列、中斷回呼、HAL 相依、兩版安裝工具、部署與還原；保存實驗版本界線 | [試驗來源快照](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/tree/main/docs/publication_supplement_20261113/uart_it/source_snapshot) |
| 獨立收音韌體 | 五秒錄音、DMA 回呼、暖機、逾時、錯誤與 CRC32；完整 FSBL 來源及 IDE 快照、上游差異 | [錄音韌體](../kws/recording_firmware/README.md) |
| 主機載入與資料蒐集 | 向量表／RAM 啟動、串列交握、完整長度及 CRC32、WAV、分類與切段 | [主機工具](../kws/recording_tools/README.md)、[資料整理](../kws/prepare_dataset.py) |
| 模型訓練演進 | 最初 MFCC／深度可分離卷積與 INT8 匯出、現場資料第二／第三版、分組定版 | [訓練歷程](../kws/training_history/README.md)、[定版快照](../kws/training_snapshot/README.md) |
| 部署除錯 | 固定 INPUT／PCM 比對程式、即時原始視窗與特徵回傳、CPU／NPU 快取修正 | [板端程式](../firmware/Src/finder_kws.c)、[比較報告](evidence/development-history/README.md) |
| 現場資料與評估 | 48 段收集清單、用途與 PCM 雜湊；五折及保留評估 | [資料清單](evidence/development-history/live_dataset_manifest_20261008.json)、[評估報告](evidence/README.md) |
| 定版產碼與部署 | 命令、內部 ONNX／量化資訊、執行階段、記憶體、建置與成功寫入驗證 | [產碼與部署證據](evidence/development-history/README.md) |
| 即時語音與視覺 | 定版六次命令接受、非命令結果；較早視覺 FOUND 紀錄，各自標示版本 | [結果說明](results.md) |
| 多工作與記憶體整合 | MDF／DMA、快取、單一 NPU 推論工作、顯示與 ISP、目標世代、連結及建置 | [工程流程](engineering-workflow.md)、[程式導讀](code-tour.md) |
| IDE 來源同步 | 原始同步工具、路徑檢查、預覽、備份、雜湊競態檢查與原子替換 | [同步工具](../tools/ide/README.md) |

## 本次 67 項材料的處理

[逐項清單](evidence/development-history/review_inventory.json)記錄每個原始路徑、雜湊、公開位置與處理狀態。[來源紀錄](evidence/development-history/source_provenance.json)另外保存這次補入檔案的原始與公開雜湊及轉換方式。

- 視覺專案已先公開的 14 份 UART 修補、部署與還原材料，已用 Git 物件雜湊對照本次原文確認一致；再補入可直接閱讀的 C／H、主程式與兩版安裝工具。
- 收音韌體、早期訓練、IDE 同步、比較及現場資料報告、定版產碼和部署紀錄已補入對應目錄。
- 現有主機收音、收集與切段工具沿用已整理的公開路徑版本；其內容與原環境不同之處不重複算成漏傳。
- SDK 的其他工具鏈啟動檔以固定上游版本索引；本庫補入 CubeIDE 的來源與設定快照，保留各檔著作權及授權索引。

先前內容雜湊盤點的 107 種差異，涵蓋備份、官方 SDK、自動產碼與建置檔，不能直接當成 107 份原創程式。這次逐項補的是實際保存的工程來源與證據。

## 已知資料範圍

- 固定五類電腦參考報告已公開；INPUT／PCM 的原始板端 CMP 逐列日誌不在本次報告內。其程式與既有開發結果摘要保留，且標明來源層級。
- course13 的指定自訂工具目錄沒有出現在本次收集結果；前期環境沿用的關係及 course14 成功模型轉換紀錄已有證據，沒有把未收集到獨立腳本寫成未做過該工作。
- 臨時終端機中執行、未另存成檔的接收、係數產生或分析程式，不能由這份報告逐字還原。現有函式、設定、報告與開發步驟已有入口，不以新寫的程式冒充歷史原檔。
- 原始錄音、模型權重、產生的模型程式與完整五映像凍結包沿用既定公開範圍；它們的角色、版本及可得雜湊分別記錄。
- 展示影片待補；本次未追加訓練、建置、燒錄或硬體驗收。

這份盤點的完整性範圍是本次提供的材料及兩個儲存庫可取得的證據，不宣稱已讀取使用者電腦上所有檔案或所有歷史對話。

