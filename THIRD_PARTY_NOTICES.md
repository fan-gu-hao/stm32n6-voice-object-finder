# 第三方來源與公開範圍

[繁體中文](THIRD_PARTY_NOTICES.md) | [English](THIRD_PARTY_NOTICES.en.md)

本專案包含多種授權，不以單一 MIT 或 Apache 授權覆蓋所有內容。各檔案原有版權、授權與第三方聲明仍然適用。

| 來源 | 用途 | 版本或紀錄 |
| --- | --- | --- |
| [ST 手部辨識範例](https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks) | 韌體框架與執行環境的基礎 | 基底提交 `6c31300`；完整本機來源記錄見 `docs/source-provenance.json` |
| [ST 實例分割範例](https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation) | 視覺整合參考 | `42f7d645f1ed61967a922defa4aa97b95d390b16` |
| [STM32 適用 YOLOv8 模型](https://github.com/stm32-hotspot/ultralytics/tree/176ecaa749b79a3f53ce077d2b14412fa45e81a0/examples/YOLOv8-STEdgeAI) | 本機使用的量化視覺模型來源 | `176ecaa749b79a3f53ce077d2b14412fa45e81a0` |
| [STM32CubeN6 錄音範例](https://github.com/STMicroelectronics/STM32CubeN6/tree/1fc803683e03b0ce78e64523441d31acd0db2829/Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder) | 獨立錄音韌體的基底 | 本機 Git 基準 `1fc803683e03b0ce78e64523441d31acd0db2829`；[修改來源與差異](kws/recording_firmware/README.md) |

元件授權索引見 [`firmware/LICENSE.md`](firmware/LICENSE.md) 與 [`vision/LICENSE.md`](vision/LICENSE.md)。原韌體索引中的 Google／Apache 模型項目來自上游手部辨識範例，不能用來判定目前 YOLO 模型的授權。

YOLO 上游的 Notice 說明 AGPL-3.0-only 與部分 ST 授權整合後的散布限制；本公開版本不提供模型權重、模型產碼或整合燒錄映像，也不宣稱具有額外散布授權。需使用第三方模型時，應依來源的實際條款取得與使用。

官方來源保留原有授權；本作品的新增與修改重點見 [`docs/code-tour.md`](docs/code-tour.md)。

獨立收音來源另保存 [STM32CubeN6 授權索引](kws/recording_firmware/LICENSE.md)與各檔原始標頭。新增的 KWS 產碼文字／JSON 是工具輸出報告與配置中繼資料，沒有包含模型權重或產生的模型 C 程式；對應工具的[原始授權索引](docs/evidence/development-history/codegen_20261008/STEdgeAI_LICENSE.txt)一併保留。
