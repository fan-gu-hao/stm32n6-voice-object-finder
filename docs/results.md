# 既有結果、原始證據與版本範圍

[繁體中文](results.md) | [English](results.en.md)

本頁依各階段實際模型與紀錄呈現結果。2026-11-13 的公開整理沒有新增訓練、建置、燒錄或板上測試。

## 分組定版的結果

| 項目 | 結果 | 原始材料 |
| --- | --- | --- |
| 五折開發驗證 | 224/227，98.68%；用於開發與選輪 | [五折報告](evidence/kws-groupcv.json) |
| 保留音訊 INT8 評估 | 15/16，93.75%；一個 cup 判為 phone，屬於單窗離線結果 | [保留測試報告](evidence/kws-int8-holdout.json) |
| 2026-10-08 板上語音操作 | cup、bottle、phone 各兩次正確接受；hello 與兩段安靜未接受命令 | [原始語音日誌](evidence/development-history/voice_groupcv_20261008.log) |
| 同輪視覺 | 保存的 53 列 FINDER 訊息皆為 found=0 | 同上；[逐列觀察摘要](evidence/development-history/observations.json) |
| 應用與 KWS 權重部署 | 既有寫入及驗證成功；位址與映像雜湊保存 | [映像清單](evidence/development-history/deployment_20261008/flash_manifest.json)、[驗證紀錄](evidence/development-history/deployment_20261008/flash_verified.json) |

定版 KWS 模型 SHA-256 為 bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b。六次命令接受是該輪操作紀錄，不代表任意環境的成功率，也不能由短時間的非命令樣本推算長期誤觸發率。

## 早期部署除錯與資料改進

早期比較使用模型 ffdec67ca044a3b8b94e8e670ee0a1f13225d00569827fdc6e20d9a1fa1bbd40，與後來分組定版分開記錄。

| 階段 | 保存的觀察 | 證據與解讀 |
| --- | --- | --- |
| 固定五類參考音訊 | 電腦參考預測、量化參數、模型與前處理係數雜湊 | [reference.json 公開副本](evidence/development-history/fixed_reference_20261007.json)；這份 JSON 本身只包含電腦參考 |
| 固定 INPUT／PCM 板端比對 | 先前開發紀錄記載五類預測與電腦一致、輸入特徵無差異、輸出最大量化差異為 1 | [比對程式](../firmware/Src/finder_kws.c)及既有開發紀錄摘要；本次收到的材料不含原始 CMP 串列逐列輸出 |
| 即時四例比對 | silence、cup、bottle、phone 的 INT8 輸入特徵皆一致；輸出最大整數差異為 0、0、3、1 | [原始比較報告](evidence/development-history/live_comparison_20261007.json)、[串列事件節錄](evidence/development-history/live_serial_events_20261007.log) |
| 安靜樣本誤判 | 該輪 silence 在板端、電腦特徵輸入與電腦 PCM 前處理三路皆判為 phone | 同份原始報告保留失敗案例，用來區分模型資料問題與移植問題 |
| 現場資料迭代 | 48 段收集完成，32 段訓練、16 段保留；逐段保存標籤、用途與 PCM 雜湊 | [現場資料清單](evidence/development-history/live_dataset_manifest_20261008.json)、[訓練版本演進](../kws/training_history/README.md) |

四例部署一致性不等於整體模型準確率。定版的比對與即時收集開關已關閉，原程式保留供閱讀當時的除錯方法。

## 早期視覺與展示範圍

[2026-10-04 視覺日誌](evidence/development-history/finder_vision_20261004.log)保存 PHONE 的 5 列及 CUP 的 8 列 found=1；逐列數量不是場景成功率，原檔的一列末尾截斷也保留。這段較早的視覺紀錄不能替代目前整合版本的三物件展示。

展示影片待補；雙模型的獨立供電、外部 Flash 自主開機與冷啟動未列為已實測項目。前期視覺作品的 A1～A5 各自有原始證據，不將其結果套用為本雙模型版本的驗證。

## 產碼與工程交付證據

[定版產碼報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)與[配置資訊](evidence/development-history/codegen_20261008/kws_network_c_info.json)記錄 ST Edge AI 內部 ONNX 階段、11 個硬體與 1 個軟體執行階段、11,409 位元組權重配置及 17,440 位元組活化值配置。這些是該次編譯統計，不是雙模型系統實測的總 RAM 峰值。

應用與 KWS 權重的兩份寫入日誌已公開；完整本機五映像交付包中的其他三份映像沿用先前內容。模型、原始錄音與燒錄映像沿用既定公開範圍。

各材料的整理方式與雜湊見[證據索引](evidence/development-history/README.md)；所有本次輸入的處理狀態見[公開內容盤點](publication-review.md)。
