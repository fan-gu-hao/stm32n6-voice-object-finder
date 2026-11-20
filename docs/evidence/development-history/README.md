# 開發歷程的原始證據

[繁體中文](README.md) | [English](README.en.md)

本目錄保存雙模型語音找物系統在錄音、模型比對、產碼、建置、寫入及板端操作期間留下的紀錄。[來源與雜湊](source_provenance.json)保存原檔及公開副本的對應；[本專案來源材料清單](review_inventory.json)索引本案來源與實際收音依賴。

## 版本與結果

| 時間／版本 | 原始材料 | 可確認的內容 |
| --- | --- | --- |
| 2026-10-04 視覺階段 | [finder_vision_20261004.log](finder_vision_20261004.log) | PHONE 與 CUP 曾輸出 `found=1`；這是較早版本的視覺紀錄 |
| 2026-10-07 固定參考 | [fixed_reference_20261007.json](fixed_reference_20261007.json) | 五類電腦參考預測、模型與係數 SHA-256、輸入／輸出量化參數 |
| 同日即時比對 | [live_comparison_20261007.json](live_comparison_20261007.json)、[串列事件](live_serial_events_20261007.log) | 同一視窗的板端與電腦特徵一致，四例輸出最大差異依序為 0、0、3、1 |
| 2026-10-08 現場收集 | [live_dataset_manifest_20261008.json](live_dataset_manifest_20261008.json) | 48 段收集完成；32 段訓練、16 段保留，逐段標籤、用途、峰值、時間與 PCM 雜湊 |
| 同日分組定版 | [config.json](codegen_20261008/config.json)、[模型 SHA-256](codegen_20261008/model_sha256.txt) | 前處理、資料方法、66 輪最終訓練、INT8 量化介面與模型版本 |
| 定版產碼 | [命令](codegen_20261008/command.json)、[日誌](codegen_20261008/codegen.log)、[報告](codegen_20261008/kws_network_generate_report.txt) | TFLite 經工具內部 ONNX／量化資訊交給 Neural-ART；硬體／軟體分工與記憶體配置 |
| 定版部署 | [建置日誌](deployment_20261008/build.log)、[映像清單](deployment_20261008/flash_manifest.json)、[驗證紀錄](deployment_20261008/flash_verified.json) | KWS 權重與應用映像的位址、雜湊及既有成功寫入驗證 |
| 定版語音操作 | [voice_groupcv_20261008.log](voice_groupcv_20261008.log) | cup、bottle、phone 各兩次接受；hello 與兩段安靜沒有接受命令；同輪視覺均為 `found=0` |

早期比較使用模型 `ffdec67ca044a3b8b94e8e670ee0a1f13225d00569827fdc6e20d9a1fa1bbd40`，係數檔 `72fe3e5f73fa012d763d53df4c8cf7ec99a4c8a75534c8d2c4b7d8068861475d`。後來分組定版模型為 `bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b`。各自結果依各自版本解讀。

## 比對如何幫助定位問題

即時比較的四類順序為 silence、cup、bottle、phone。四例都記錄 `input_diff=0`、`input_max=0`，表示板端 C 前處理與電腦在這些相同 PCM 視窗上產生一致的 INT8 特徵。輸出最大差異是量化整數的差值，並非百分比誤差。

其中 silence 在板端、電腦直接特徵推論、電腦 PCM 完整前處理三條路徑均判成 phone。這份失敗案例保留了當時的模型問題，並與後續[訓練版本演進](../../../kws/training_history/README.md)和現場資料收集連在一起；不能把較早錯誤抹掉，也不能把四個視窗的部署一致性當作泛化準確率。

固定五類的 `reference.json` 是電腦參考資料，本身沒有板端 INPUT／PCM 逐列輸出。2026-11-20 已從原始開發對話重新讀到實際 CMP 輸出：[覆核與節錄](../../original-history-review.md)保存其工程解讀，兩路各五類正確、PCM 路徑每例 637 個 INT8 特徵一致，輸出最大整數差異為 0，silence 為 1。節錄來自對話中貼上的終端結果，不是重新取得的完整原始串列日誌；與此處的電腦參考 JSON 分開標示。

## 產碼、記憶體與寫入

ST Edge AI 4.0.1 接收定版 INT8 TFLite，內部建立 `kws_int8_OE_3_3_1.onnx` 與[量化中繼資料](codegen_20261008/kws_int8_OE_3_3_1_Q.json)，再呼叫 Neural-ART 1.1.3-275。這是本專案 KWS 量化模型在 N6 編譯工具內的中間表示。

[編譯配置資訊](codegen_20261008/kws_network_c_info.json)與文字報告記錄：

- 12 個執行階段：11 個純硬體、1 個軟體 Softmax，沒有混合階段，也沒有執行階段控制器指令包。
- KWS 權重配置 11,409 位元組，活化值配置 17,440 位元組；分別放入 64 KiB `kwsFlash` 與 256 KiB `kwsRAM` 池。
- 報告的執行環境額外程式／唯讀資料為 40,870 位元組，額外 RAM 為 29 位元組。這些是該次 KWS 產碼報告的統計，不能直接當成雙模型系統總記憶體峰值。

兩份 [KWS 寫入日誌](deployment_20261008/flash_kws_weights.bin.log)與[應用寫入日誌](deployment_20261008/flash_finder_signed.bin.log)均保存成功驗證訊息。對應位址為 `0x70700000` 與 `0x70100000`。檔名中的 `signed` 沿用原工具命名；既有封裝採無金鑰模式，不據此宣稱密碼學簽章。

## 紀錄格式與公開範圍

JSON 與文字紀錄將本機專案前綴、工具前綴及偵錯器序號替換為佔位文字，去除終端控制碼；模型雜湊、數值、錯誤案例與映像驗證結果保持原樣。原始模型、ONNX 模型檔、權重、映像與個人錄音未加入本庫；公開的兩份編譯 JSON 為圖形、量化參數與配置資訊。

即時串列原檔的匯出報告已省略 1,181 列 `LIVE,D` 封包，公開節錄另外省略一列殘留十六進位片段；因此命名為事件節錄，不能拿它重新驗證完整 PCM 傳輸的 CRC32。原檔與節錄的雜湊分別保留。日誌開頭已有前一輪的殘留事件，後續才出現完整的四例收集；沒有將兩段混算。

[日誌觀察摘要](observations.json)由保存文字解析而來。較早視覺日誌有一列末尾截斷，原樣保留；逐列數量不是場景辨識率。展示影片待補；這些材料不包含雙模型獨立供電與冷啟動的實測通過紀錄。
