# 既有結果、原始證據與版本範圍

[繁體中文](results.md) | [English](results.en.md)

本頁整理雙模型語音找物系統的既有開發與定版結果，依模型版本及測試方法分開呈現。數據來自保存的評估報告、建置與寫入日誌、板端操作紀錄，以及重新核對的原始對話與附件；後者的定位與證據界線見[原始開發歷程審閱](original-history-review.md)。

## 分組定版的結果

| 項目 | 結果 | 原始材料 |
| --- | --- | --- |
| 五折 INT8 開發驗證 | 224/227，98.68%；各折結果合計，用於開發與選輪 | [五折報告](evidence/kws-groupcv.json) |
| 定版保留音訊評估 | 浮點與 INT8 皆為 15/16，93.75%；16 段的分類結果一致，一個 cup 判為 phone | [保留測試報告](evidence/kws-int8-holdout.json) |
| 保留音訊的單窗分數條件 | 12 段命令中，11 段分類正確且通過分數條件；4 段非命令的誤通過為 0 | [原始訓練輸出定位](original-history-review.md)；尚未套用板上的音量門檻、連續命中與冷卻規則 |
| 2026-10-08 板上語音操作 | cup、bottle、phone 各兩次正確接受；hello 與兩段安靜未接受命令 | [原始語音日誌](evidence/development-history/voice_groupcv_20261008.log) |
| 同輪視覺 | 保存的 53 列 FINDER 訊息皆為 found=0 | 同上；[逐列觀察摘要](evidence/development-history/observations.json) |
| 應用與 KWS 權重部署 | 應用寫入 0x70100000、KWS 權重寫入 0x70700000 並驗證成功；映像雜湊保存 | [映像清單](evidence/development-history/deployment_20261008/flash_manifest.json)、[驗證紀錄](evidence/development-history/deployment_20261008/flash_verified.json) |

定版 KWS 模型 SHA-256 為 bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b。日誌保留候選命中、命令接受與 FINDER 目標的連續紀錄。六次接受後的目標皆與命令一致；首次 cup 接受前目標已為 CUP，後續五次可見類別切換。六次接受描述該輪操作，不代表任意環境的成功率，也不能由短時間的非命令樣本推算長期誤觸發率。

保留音訊中判錯的 `cup/take_45.wav`，INT8 模型最高的 phone 分數為 60.9375%，低於 90% 命令分數門檻。因此「分類判成 phone」不等於「系統接受了錯誤的 phone 命令」。15/16 是單窗分類結果，11/12 與 0/4 是離線分數條件的檢查，六次正確接受則是另一輪板上操作紀錄；三者不可合併成同一個成功率。

分組訓練原始附件保留第 5 折的後段、五折彙總、最終重訓第 1～66 輪，以及浮點／INT8 保留音訊結果。五折最佳輪數為 `[82, 28, 66, 9, 79]`，以中位數 66 在全部 227 段開發資料上重訓。這直接補證定版訓練完成，但不是五折每一輪都完整保存的訓練日誌。

## 早期部署除錯與資料改進

早期比較使用模型 ffdec67ca044a3b8b94e8e670ee0a1f13225d00569827fdc6e20d9a1fa1bbd40，與後來分組定版分開記錄。

| 階段 | 保存的觀察 | 證據與解讀 |
| --- | --- | --- |
| 早期實際使用失敗 | 即時辨識曾偏向 phone，與預期命令或環境不符，因而增加固定輸入與現場音訊診斷 | [原始開發歷程審閱](original-history-review.md)；不把後來的定版結果倒推為初版已可靠 |
| 固定五類參考音訊 | 電腦參考預測、量化參數、模型與前處理係數雜湊 | [reference.json 公開副本](evidence/development-history/fixed_reference_20261007.json)；這份 JSON 本身只包含電腦參考 |
| 固定 INPUT／PCM 比較結果 | 直接輸入 INT8 特徵與從 PCM 重算兩路，五類均各 5/5 分類正確；每例 637 個特徵的差異數與最大差異皆為 0。兩路皆只有 silence 的輸出最大整數差異為 1，其餘為 0 | [比對程式](../firmware/Src/finder_kws.c)、[原始 CMP 輸出定位](original-history-review.md)；原始對話有 `CMP,BEGIN` 至 `CMP,END` 的十列結果，不再僅是方法說明 |
| 即時四例比對 | silence、cup、bottle、phone 的 INT8 輸入特徵皆一致；輸出最大整數差異為 0、0、3、1 | [原始比較報告](evidence/development-history/live_comparison_20261007.json)、[串列事件節錄](evidence/development-history/live_serial_events_20261007.log) |
| 安靜樣本誤判 | 該輪 silence 在板端、電腦特徵輸入與電腦 PCM 前處理三路皆判為 phone | 同份原始報告保留失敗案例，用來區分模型資料問題與移植問題 |
| 加入四段現場樣本重訓 | 原訓練 142 段增加為 146 段，驗證仍為 49 段；浮點與 INT8 皆為 48/49（97.96%） | [訓練原始輸出定位](original-history-review.md)、[當時訓練程式](../kws/train_kws.py)；四段補訓樣本的回看已參與訓練，不算獨立驗證 |
| 現場資料迭代 | 48 段收集完成，32 段訓練、16 段保留；逐段保存標籤、用途與 PCM 雜湊 | [現場資料清單](evidence/development-history/live_dataset_manifest_20261008.json)、[訓練版本演進](../kws/training_history/README.md) |

固定參考與四例現場診斷分屬不同輸入，不能因固定五類通過就忽略現場安靜樣本誤判。數值一致性支持這些樣本上的移植正確性，不等於整體模型準確率；它也讓後續改進聚焦於資料與訓練。現場第三版訓練程式已保存，但尚未找到該版本獨立完成的訓練日誌，不為它另列完成指標。定版的比對與即時收集開關已關閉，原程式保留供閱讀當時的除錯方法。

## 早期視覺與展示範圍

[2026-10-04 視覺日誌](evidence/development-history/finder_vision_20261004.log)保存 PHONE 的 5 列及 CUP 的 8 列 found=1；逐列數量不是場景成功率，原檔的一列末尾截斷也保留。這段較早的視覺紀錄不能替代目前整合版本的三物件展示。

[實機展示影片](https://youtu.be/m7wET9g5u6k)已提供；雙模型的獨立供電、外部 Flash 自主開機與冷啟動未列為已實測項目。

## 產碼與工程交付證據

[定版產碼報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)與[配置資訊](evidence/development-history/codegen_20261008/kws_network_c_info.json)記錄 ST Edge AI 內部 ONNX 階段、11 個硬體與 1 個軟體執行階段、11,409 位元組權重配置及 17,440 位元組活化值配置。這些是該次編譯統計，不是雙模型系統實測的總 RAM 峰值。

[定版建置日誌](evidence/development-history/deployment_20261008/build.log)記錄應用 SRAM 535,544 位元組、視覺指令 Flash 230,528 位元組、應用／顯示 PSRAM 8,949,920 位元組。KWS RAM 保留區由產碼使用絕對位址配置，不能將連結器顯示的 0 位元組解讀為未使用；區域位址、容量與用量對照見[程式導讀](code-tour.md)。

[KWS 權重寫入日誌](evidence/development-history/deployment_20261008/flash_kws_weights.bin.log)與[應用寫入日誌](evidence/development-history/deployment_20261008/flash_finder_signed.bin.log)均記錄成功驗證。這輪實際更新兩份映像；本機五映像交付包的 FSBL、視覺權重與視覺指令沿用既有內容，不能把兩份寫入日誌解讀為同輪重寫並驗證了五份映像。模型、原始錄音與燒錄映像的公開範圍見[第三方說明](../THIRD_PARTY_NOTICES.md)。

各材料的整理方式與雜湊見[證據索引](evidence/development-history/README.md)，來源對應見[本專案來源材料清單](evidence/development-history/review_inventory.json)。
