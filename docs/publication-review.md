# 公開內容、來源與建置依賴

[繁體中文](publication-review.md) | [English](publication-review.en.md)

> **版本編號說明：**`Runtime1100`、`Runtime1200`、`Runtime1201` 分別代表 ST 神經網路執行函式庫（Network Runtime）的 **11.0.0、12.0.0、12.0.1** 版本。這套函式庫在建置時連結進韌體，提供模型程式所需的執行支援；更新模型產碼工具時，也須配對函式庫、標頭檔與神經網路處理器（NPU）支援程式。這些編號與 ST Edge AI 工具本身的版本號分開記錄。 [版本配對詳解](toolchain-compatibility.md)。

本儲存庫提供 STM32N6 雙模型語音找物系統的應用、資料處理、模型訓練、板端整合與部署材料。主應用位於 `firmware/`；`kws/` 包含語音資料流程、模型訓練、收音韌體與主機工具；`vision/` 保存視覺部署採用的實例分割參考來源。各部分的程式入口、來源歸屬及完整建置所需材料列於下文。

## 各部分提供什麼

| 部分 | 公開內容 | 閱讀入口 |
| --- | --- | --- |
| 雙模型應用 | NPU 依序使用、語音接受、目標切換、連續幀確認、相機與 LCD 協作 | [app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c) |
| 連續音訊與 C 前處理 | MDF／循環 DMA、環形視窗、快取、MFCC、量化介面與分層比對 | [finder_mic.c](../firmware/Src/finder_mic.c)、[finder_kws.c](../firmware/Src/finder_kws.c) |
| 資料蒐集工具 | 五秒錄音韌體、RAM 啟動、串列接收、長度及 CRC32 檢查 | [錄音來源](../kws/recording_firmware/README.md)、[主機工具](../kws/recording_tools/README.md) |
| 資料與訓練 | 分類錄音、切段、來源分組、特徵、資料增強、五折驗證及量化 | [collect_n6.py](../kws/collect_n6.py)、[prepare_dataset.py](../kws/prepare_dataset.py)、[訓練歷程](../kws/training_history/README.md)、[定版快照](../kws/training_snapshot/README.md) |
| 模型轉換與部署 | 視覺 Python／PyTorch 匯出、ONNX／SavedModel 轉換、每通道 INT8 量化、N6 產碼、執行期對齊與後處理移植；KWS 網路名稱、記憶體池、產碼命令、工具內部 ONNX 與配置報告 | [完整視覺流程](../vision/deployment/README.md)、[視覺與語音流程](engineering-workflow.md)、[KWS 部署設定](../kws/deployment/README.md)、[產碼紀錄](evidence/development-history/README.md) |
| 系統建置 | 模型與 DSP 建置清單、記憶體分區、獨立指令映像及 IDE 入口 | [Makefile](../firmware/Makefile)、[kws.mk](../firmware/mks/kws.mk)、[連結腳本](../firmware/Gcc/STM32N657xx.ld)、[建置說明](build.md) |
| 結果與版本 | 分組評估、保留音訊、即時比較、收集清單、語音／視覺日誌與寫入驗證 | [結果](results.md)、[證據索引](evidence/README.md) |
| 開發工具 | IDE 來源同步、路徑檢查、預覽、備份、競態檢查與原子替換 | [IDE 工具](../tools/ide/README.md) |
| 主機診斷與部署流程 | 固定資料參考匯出、即時音訊／特徵比對、現場資料收集、定版產碼安裝、封裝與寫入驗證 | [開發流程原始碼](../tools/development-history/README.md)、[來源與公開差異](../tools/development-history/source-provenance.json) |

## 32 步開發流程與程式對應

[完整開發流程](development-steps.md)依 32 個步驟呈現功能定義、視覺匯出、量化、N6 產碼與後處理、語音資料與訓練量化、雙模型記憶體及即時系統、數值除錯、資料迭代、部署與展示。[步驟與原始碼清單](development-source-map.json)逐項對應現有程式、設定及結果；首頁呈現 8 個開發重點，詳細文件保留完整 32 步，原始碼索引提供實作入口。

本次補入原先散落於開發對話程式區塊的[主機端流程](../tools/development-history/README.md)。公開檔案抽取自當時的完整程式，保留診斷模式切換、參考資料建立、資料收集、產物同步及部署處理。裝置識別改由環境變數提供，來源紀錄保存原程式區塊、抽出本文與公開版本的雜湊及差異。既有核心韌體、訓練程式、記憶體設定及實測紀錄繼續保留。

這些流程快照的環境相依與歷史完成狀態逐檔列出；例如定版產碼與後續檔案搜尋檢查分開記錄，並提供當時的修正流程。模型產碼本體、權重及預建映像的可得範圍，仍在下方建置材料與來源清單中明列。

## 工程實作與來源分工

本專案實作包括五分類語音資料與模型建立、現場資料迭代、Python／C 特徵移植、連續收音、量化介面檢查、CPU／DMA／NPU 快取處理、視覺模型匯出、量化、N6 產碼與執行期對齊、相機中斷佇列適配、兩模型共同建置、搜尋狀態與跨工作資料交接、記憶體配置及部署驗證。函式與檔案對應見[程式導讀](code-tour.md)。

KWS 模型由本專案建立、訓練與量化。視覺部分也由作者親自完成 Python／PyTorch `.pt` 模型處理與匯出，經 ONNX、TensorFlow SavedModel 與每通道 INT8 TFLite，再進行 ST Edge AI／Neural-ART 產碼、執行期配對、產物移植及應用整合。[視覺完整流程](../vision/deployment/README.md)連結準備階段的匯出、量化紀錄與雙模型部署實作，各階段模型及產碼輸入版本另按來源紀錄保存。ST 手部雙模型範例提供 FreeRTOS、相機、顯示與推論執行環境的底座；ST 實例分割範例提供模型介面與後處理。HAL、BSP、CMSIS-DSP、FreeRTOS 及 STAI／ATON 保留版本、原始檔頭與授權索引，詳見[第三方來源](../THIRD_PARTY_NOTICES.md)、[產碼輸入紀錄](../sources.txt)及[來源版本](source-provenance.json)。

分類收集程式使用的獨立錄音元件原先位於 `course15_n6_mic_test`。本庫保存它作為資料蒐集依賴，並保留原始版本及上游差異。訓練快照與錄音 IDE 快照也保留當時的路徑及環境假設，使用方式由各目錄說明。

## 來源材料與雜湊

[本專案來源材料清單](evidence/development-history/review_inventory.json)追溯 25 項雙模型原始材料與 23 項收音依賴材料的來源及公開位置。這 48 項是選定開發材料的盤點數；儲存庫檔案總數另計。[補充來源紀錄](evidence/development-history/source_provenance.json)保存原始／公開雜湊、路徑替換與節錄方式；[評估來源](evidence/provenance.json)保存定版訓練與評估檔案的追溯資訊。

模型比較、語音接受與視覺紀錄依各自版本呈現；固定電腦參考 JSON、板端比較程式與原始串列日誌分別保存，對應用途與結果見[測試紀錄](results.md)。

2026-11-20 逐輪整理兩篇原始開發對話與附件，補充收音啟動、視覺產碼、封裝對齊、固定五類比對及模型迭代。[開發歷程](original-history-review.md)將實際終端輸出、修正方案及尚無執行結果的步驟分開標示。公開材料限於工程摘要與必要的去識別化輸出節錄；私人對話全文及早期原始壓縮附件未隨庫提供。上述 48 項清單的範圍維持為原始檔案盤點，對話附件另依開發歷程說明。

## 2026-11-20 材料完整性檢查與文件補充

以提交 `cc42386d9dba5ee3896b9b1547de3fc125046b6b` 為檢查基準，既有 48 項來源材料中，45 項映射至本儲存庫的檔案全部存在，其餘 3 項連到固定 STM32CubeN6 SDK 來源。來源追溯紀錄中的 40 項公開版本 SHA-256 亦全部符合；已記錄的原文與公開版差異包括路徑參數化、裝置識別移除及日誌節錄。逐項結果見[公開內容盤點](evidence/publication_audit_20261120.json)。檢查範圍為已盤點的自主應用、資料／訓練與收音依賴；第三方 SDK 的逐行審查不在此次範圍內。

完整 GCC／LCD 建置清單另完成靜態來源盤點：11 份建置清單展開 132 個 C／組合語言來源，其中 128 個已在庫，4 個為公開範圍外的 YOLO／KWS 產碼；對應模型標頭與包含目錄也須由同一組外部依賴提供。主應用與 GCC 支援來源、6 個 finder 標頭、Runtime1201 與 NemaGFX 函式庫均已確認存在。

[視覺產碼腳本與配置參考](../vision/deployment/README.md)提供固定官方提交的三個原檔、雜湊、來源與授權；上游參考快照與本機歷史產物分別標示。[雙模型記憶體與部署](memory-deployment.md)及[工具鏈相容性](toolchain-compatibility.md)另以中英雙語說明配置、版本整合與封裝修正，首頁提供配置表與摘要。

該次整理維持既有韌體與訓練運算邏輯；Makefile 的變動限於釐清「同時執行一個模型」的註解，兩模型依序共用 NPU 的設定保持不變。記錄的工作為來源、配置及文件整理，未重新執行訓練、產碼或燒錄。

## 完整建置所需材料

公開庫提供原始碼、設定與工程紀錄。完整建置另需匹配版本的視覺／KWS 模型產碼與權重、對應執行環境及所需 SDK；原始錄音與預建燒錄映像不隨庫提供。定版部署指標、映像角色、位址與可得雜湊則保存於文件及證據中。

編譯器、工具版本與入口見[建置說明](build.md)。[實機展示影片](https://youtu.be/m7wET9g5u6k)已提供；公開文件保留既有結果，韌體功能與原始測試數據維持定版內容。
