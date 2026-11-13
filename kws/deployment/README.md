# KWS 模型產碼配置

這兩份配置直接複製自定版模型的產碼工作目錄，未修改內容。

| 檔案 | 用途 |
| --- | --- |
| [kws_neuralart.json](kws_neuralart.json) | Neural-ART 設定檔，選用 `kws` 配置及 `kws.mpool` |
| [kws.mpool](kws.mpool) | KWS 記憶體區域、存取屬性與容量 |

| 區域 | 起點 | 容量 |
| --- | --- | --- |
| KWS 暫存區 | `0x91FC0000` | 256 KiB |
| KWS 權重區 | `0x70700000` | 64 KiB |

搭配環境為 ST Edge AI 4.0.1。既有定版紀錄中的模型產碼命令如下；工作目錄需同時具備這兩份配置與對應模型：

    stedgeai generate --model kws_int8.tflite --target stm32n6 --name kws_network --st-neural-art kws@kws_neuralart.json --input-data-type int8 --output-data-type int8

對應模型 SHA-256：`bc0612680d3e9efc4e5036a433a94d88b20344be4208545c9817ebacb6585b0b`。

這裡提供配置與既有命令紀錄，不包含模型權重，也不會自動產碼。前處理與量化係數見 [`finder_kws_tables.h`](../../firmware/Inc/finder_kws_tables.h)。
