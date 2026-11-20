# 公開內容、來源與建置依賴

[繁體中文](publication-review.md) | [English](publication-review.en.md)

本儲存庫保存 STM32N6 雙模型語音找物系統的應用、資料處理、模型訓練、板端整合與部署紀錄。主應用位於 `firmware/`；`vision/` 保存採用的官方實例分割參考來源；`kws/` 保存語音資料流程、訓練程式與收音依賴。

## 各部分提供什麼

| 部分 | 公開內容 | 閱讀入口 |
| --- | --- | --- |
| 雙模型應用 | NPU 依序使用、語音接受、目標切換、連續幀確認、相機與 LCD 協作 | [app.c](../firmware/Src/app.c)、[app_cam.c](../firmware/Src/app_cam.c) |
| 連續音訊與 C 前處理 | MDF／循環 DMA、環形視窗、快取、MFCC、量化介面與分層比對 | [finder_mic.c](../firmware/Src/finder_mic.c)、[finder_kws.c](../firmware/Src/finder_kws.c) |
| 資料蒐集依賴 | 五秒錄音韌體、RAM 啟動、串列接收、長度及 CRC32 檢查 | [錄音來源](../kws/recording_firmware/README.md)、[主機工具](../kws/recording_tools/README.md) |
| 資料與訓練 | 分類錄音、切段、來源分組、特徵、資料增強、五折驗證及量化 | [collect_n6.py](../kws/collect_n6.py)、[prepare_dataset.py](../kws/prepare_dataset.py)、[訓練歷程](../kws/training_history/README.md)、[定版快照](../kws/training_snapshot/README.md) |
| 模型部署 | KWS 網路名稱、記憶體池、產碼命令、工具內部 ONNX 與配置報告 | [部署設定](../kws/deployment/README.md)、[產碼紀錄](evidence/development-history/README.md) |
| 系統建置 | 模型與 DSP 建置清單、記憶體分區、獨立指令映像及 IDE 入口 | [Makefile](../firmware/Makefile)、[kws.mk](../firmware/mks/kws.mk)、[連結腳本](../firmware/Gcc/STM32N657xx.ld)、[建置說明](build.md) |
| 結果與版本 | 分組評估、保留音訊、即時比較、收集清單、語音／視覺日誌與寫入驗證 | [結果](results.md)、[證據索引](evidence/README.md) |
| 開發工具 | IDE 來源同步、路徑檢查、預覽、備份、競態檢查與原子替換 | [IDE 工具](../tools/ide/README.md) |

## 程式來源與實作範圍

ST 手部雙模型範例提供 FreeRTOS、相機、顯示與推論執行環境的底座；ST 實例分割範例提供所選視覺模型的介面與後處理。HAL、BSP、CMSIS-DSP、FreeRTOS 及 STAI／ATON 沿用上游元件。其版本、原始檔頭與授權索引保留，詳見[第三方來源](../THIRD_PARTY_NOTICES.md)、[模型來源](../sources.txt)及[來源版本](source-provenance.json)。

本專案實作包括五分類語音資料與模型建立、現場資料迭代、Python／C 特徵移植、連續收音、量化介面檢查、CPU／DMA／NPU 快取處理、兩模型共同建置、搜尋狀態與跨工作資料交接、記憶體配置及部署驗證。函式與檔案對應見[程式導讀](code-tour.md)。

分類收集程式使用的獨立錄音元件原先位於 `course15_n6_mic_test`。本庫保存它作為資料蒐集依賴，並保留原始版本及上游差異。訓練快照與錄音 IDE 快照也保留當時的路徑及環境假設，使用方式由各目錄說明。

## 來源材料與雜湊

[本專案來源材料清單](evidence/development-history/review_inventory.json)涵蓋 25 項雙模型原始材料與 23 項收音依賴材料；它用於追溯來源與公開位置，不是整個儲存庫的檔案總數。[補充來源紀錄](evidence/development-history/source_provenance.json)保存原始／公開雜湊、路徑替換與節錄方式；[評估來源](evidence/provenance.json)保存定版訓練與評估檔案的追溯資訊。

模型比較、語音接受與視覺紀錄依各自版本呈現。固定電腦參考 JSON、板端比較程式與原始串列日誌是不同材料，結果解讀見[測試紀錄](results.md)。

## 完整建置所需材料

公開庫提供原始碼、設定與工程紀錄。完整建置另需匹配版本的視覺／KWS 模型產碼與權重、對應執行環境及所需 SDK；原始錄音與預建燒錄映像不隨庫提供。定版部署指標、映像角色、位址與可得雜湊則保存於文件及證據中。

編譯器、工具版本與入口見[建置說明](build.md)。展示影片待補；公開文件保留既有結果，韌體功能與原始測試數據維持定版內容。
