# 公開內容與本機證據盤點

整理日期：2026-11-13。核對基準為視覺專案 259bd0b2a3f5cbe4260509b0786d39806ff80c50 與雙模型專案 49c3e7abce1c4bf4601bd62f4fe9122e1d844951，以及已保存的開發紀錄。這次更新補足文件、程式入口與跨階段證據關係，不變更定版韌體。

## 已公開且可直接閱讀

| 範圍 | 已保存內容 | 入口 |
| --- | --- | --- |
| 視覺模型匯出 | ONNX、onnx2tf、SavedModel／TFLite 的實際成功日誌與工具版本 | [原始日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log) |
| 視覺量化與適配 | ST 量化設定與結果、模型介面、三模型比較、模型庫與封裝修補 | [前期工程導覽](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/main/docs/engineering-workflow.md) |
| 視覺工程驗證 | A1 來源重建、A2 數值／框／遮罩、A3 效能、A4 記憶體、A5 可靠性 | [視覺專案](https://github.com/fan-gu-hao/stm32n6-instance-segmentation) |
| 收音與主機工具 | RAM 啟動、串列交握與 CRC32、資料收集、切段 | [工具](../kws/recording_tools/README.md)、[資料整理](../kws/prepare_dataset.py) |
| 模型與資料方法 | KWS 架構、MFCC、增強、分組與排重、現場重訓版本、定版快照 | [訓練程式](../kws/)、[定版快照](../kws/training_snapshot/README.md) |
| 板端部署除錯 | INPUT／PCM 比對、即時 PCM／特徵／輸出擷取、快取與介面檢查 | [finder_kws.c](../firmware/Src/finder_kws.c) |
| 系統整合 | MDF／DMA、FreeRTOS 三工作、雙模型、目標狀態、顯示、連結與建置 | [完整工程導覽](engineering-workflow.md)、[程式導讀](code-tour.md) |
| 評估與來源 | 五折、保留測試、模型配置、來源與公開副本雜湊 | [評估報告](evidence/README.md)、[來源紀錄](source-provenance.json) |

## 已做過、原始檔仍在本機的部分

下列項目在開發過程已存在或有執行紀錄，公開版目前以程式、摘要或來源位置呈現。沒有把尚未附原始檔解讀成未完成，也沒有把摘要當成新取得的原始日誌。

| 材料 | 已知本機位置，均相對於對應原專案 | 目前公開狀態 |
| --- | --- | --- |
| course15 收音韌體 | STM32CubeN6/Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder/ | 主機啟動與接收工具已公開；修改後的獨立錄音韌體尚未隨本庫附上 |
| 早期固定 KWS 比對 | kws/comparison/20261007_192902_246036/reference.json 及對應板端輸出 | 比對程式與參考標頭已公開；開發結果見結果說明 |
| 即時 PCM／MFCC／推論比對 | kws/live_comparison/20261007_201024_942174/result.json、serial.log | 產生與傳送邏輯已公開；原始比較報告仍在本機 |
| 現場資料收集紀錄 | kws/live_datasets/20261008_005213_207370/manifest.json、serial.log | 收集計畫、板端收集程式、訓練與保留測試報告已公開；原始錄音與完整收集紀錄未附 |
| 定版即時語音日誌 | logs/voice_groupcv_20261008_025732_533540.log | [結果摘要](results.md)已列六次命令接受與非命令測試的範圍 |
| 早期視覺找物日誌 | logs/finder_vision_20261004_200926.log | [結果摘要](results.md)已列較早 CUP／PHONE 找到的紀錄 |
| 定版產碼與部署紀錄 | output/finder_groupcv_codegen_20261008_022527_741465/、output/finder_groupcv_deploy_20261008_025657_154175/ | 模型配置、建置來源與概要已公開；完整產碼、映像及部分原始報告在本機 |
| 完整凍結包 | releases/finder_groupcv_20261008_frozen_20261009/ | 五映像的交付角色已在工程流程記錄；映像未加入本公開版 |
| IDE 同步工具 | 原專案根目錄 sync_cubeide_sources.py | 整理後的 IDE 專案與建置入口已公開；原同步輔助工具未附 |

若需要再擴充程式展示，應從上述原始位置核對現有主機腳本、文字報告和修改差異，逐項補入公開目錄並記錄來源；不重新創作一份腳本冒充原始開發產物。原始 output 目錄下是否另有獨立保存的接收器、係數產生器或評估腳本，仍需依本機清單確認。

## 文件這次補足的重點

- 將原始模型、ONNX、量化、三模型比較、模型庫修補、N6 編譯與部署連成完整流程。
- 將前期視覺與收音工作，連到本版 KWS、雙模型及記憶體整合。
- 展開資料隔離、CPU／DMA／NPU 快取、分層比對、狀態機、工作與緩衝協調等實作。
- 保留歷史試驗與定版的關係；各版本使用各自的模型雜湊與測試結果。
- 原始記錄仍在本機的部分列出位置與公開狀態，方便後續補上來源。

模型權重、個人錄音、資料集與整合燒錄映像沿用既定公開範圍；本頁的盤點不更改各元件的授權。展示影片仍待補。
