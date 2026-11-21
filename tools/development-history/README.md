# 雙模型開發時的主機流程原碼

[繁體中文](README.md) | [English](README.en.md)

> **版本編號說明：**`Runtime1100`、`Runtime1200`、`Runtime1201` 分別代表 ST 神經網路執行函式庫（Network Runtime）的 **11.0.0、12.0.0、12.0.1** 版本。這套函式庫在建置時連結進韌體，提供模型程式所需的執行支援；更新模型產碼工具時，也須配對函式庫、標頭檔與神經網路處理器（NPU）支援程式。這些編號與 ST Edge AI 工具本身的版本號分開記錄。 [版本配對詳解](../../docs/toolchain-compatibility.md)。

本目錄補齊視覺產碼與正式工程移植、封裝對齊、固定數值比對、即時資料收集、KWS 產碼、安裝建置與部署的主機端實作。33 份程式取自當時對話中實際提供的完整 Python 或殼層（Shell）區塊；原本直接貼入終端機，Python 使用多行輸入（here-document），公開時依用途命名，並非原電腦已有這些同名檔案。

這些是各開發階段的流程快照，會讀取當時的模型、係數、目錄及版本指標。部分檔案會修改韌體來源、切換診斷模式、建置或直接燒錄；適用版本及動作列於下表。定版應用程式位於 [`firmware/`](../../firmware/)，目前建置入口見[建置說明](../../docs/build.md)。

本目錄的視覺腳本保存雙模型工程的 N6 產碼與整合階段。作者更前面的 **Python／PyTorch → ONNX → SavedModel → 逐通道 INT8 TFLite** 工作同屬完整視覺流程，實作依據包括[匯出日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/03_export_seg.log)、[量化設定](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/configs/yolov8n_seg_int8_int8.yaml)及[量化日誌](https://github.com/fan-gu-hao/stm32n6-instance-segmentation/blob/259bd0b2a3f5cbe4260509b0786d39806ff80c50/results/checkpoints/2026-09-09/logs/04_st_quantization_seg.log)。模型準備、驗證、產碼與韌體交接順序見[完整視覺流程](../../vision/deployment/README.md)。

## 步驟、動作與當時結果

| 對應開發步驟 | 原碼 | 用途與實際動作 | 當時結果／紀錄 |
| --- | --- | --- | --- |
| 2、3 | [vision_01_prepare_vision.sh](vision_01_prepare_vision.sh) | **建立視覺參考工程**：建立 course17 視覺目錄、取得固定參考來源及模型輸入，保存來源與工具版本。 | 後續回貼確認取得 3,514,494 B 模型，ST Edge AI 為 4.0.1。 [紀錄1](../../sources.txt)、[紀錄2](../../docs/engineering-workflow.md) |
| 4 | [vision_02_match_vision_runtime.py](vision_02_match_vision_runtime.py) | **配對視覺執行期**：替換視覺參考工程執行期，加入 Flash／PSRAM 區段巨集。 | 後續回貼確認 Runtime1201 與兩類區段設定完成。 [紀錄1](../../docs/toolchain-compatibility.md)、[紀錄2](../../vision/deployment/README.md) |
| 3、11 | [vision_03_generate_and_build_vision.sh](vision_03_generate_and_build_vision.sh) | **產生 YOLO 並建置參考工程**：執行 N6 產碼、參考工程建置，抽出應用與視覺指令，封裝映像。 | vision_20261004_181810 的產碼、ELF 連結與封裝回報成功。 [紀錄1](../../docs/engineering-workflow.md)、[紀錄2](../../vision/deployment/README.md) |
| 2、5 | [vision_04_prepare_main_firmware.sh](vision_04_prepare_main_firmware.sh) | **建立正式主工程**：建立 firmware 底座並複製這次視覺產碼的模型輸入。 | 後續回貼確認正式主工程建立及模型複製完成。 [紀錄1](../../docs/source-provenance.json)、[紀錄2](../../docs/engineering-workflow.md) |
| 3、5 | [vision_05_copy_vision_artifacts.sh](vision_05_copy_vision_artifacts.sh) | **移入六項視覺產物**：將本案產生的網路、模型介面、執行指令及權重移入正式工程。 | 後續回貼逐項列出六份來源與目的地，複製完成。 [紀錄1](../../docs/engineering-workflow.md)、[紀錄2](../../firmware/mks/ai.mk) |
| 4 | [vision_06_match_main_runtime.py](vision_06_match_main_runtime.py) | **配對正式工程執行期**：同步更新正式工程的標頭、函式庫與 NPU 支援來源。 | 後續回貼確認三個目錄更新與 GCC Runtime1201 配對完成。 [紀錄1](../../firmware/mks/ai.mk)、[紀錄2](../../docs/toolchain-compatibility.md) |
| 5 | [vision_07_update_model_build_list.py](vision_07_update_model_build_list.py) | **替換模型建置清單**：修改 Makefile，將手部模型建置項目換成本案 YOLO 網路與 STAI 介面。 | 後續回貼的 Makefile 列出 network.c 與 stai_network.c。 [紀錄1](../../firmware/Makefile)、[紀錄2](../../docs/engineering-workflow.md) |
| 7 | [vision_08_import_postprocessing.py](vision_08_import_postprocessing.py) | **移入後處理來源**：複製後處理核心與轉接來源，修改對應編譯清單。 | 後續回貼確認兩個來源目錄與轉接層建置清單完成。 [紀錄1](../../firmware/mks/ai.mk)、[紀錄2](../../firmware/Lib/ai-postprocessing-wrapper/app_postprocess_iseg_yolo_v8_ui.c) |
| 7 | [vision_09_configure_postprocessing.py](vision_09_configure_postprocessing.py) | **配置視覺輸出與門檻**：設定類別、候選位置、遮罩原型及後處理門檻。 | 回貼列出 80 類、1,344 候選、32 個係數、64 遮罩尺寸，以及 0.50／0.40／10 設定。 [紀錄1](../../firmware/Inc/postprocess_conf.h)、[紀錄2](../../docs/engineering-workflow.md) |
| 5 | [vision_10_update_main_model_info.py](vision_10_update_main_model_info.py) | **更新主程式模型資訊**：改接模型標頭及開機時顯示的視覺模型資訊。 | 後續 main.c 回貼包含 stai_network.h 與 Vision model 列印。 [紀錄1](../../firmware/Src/main.c) |
| 5、7、10 | [vision_11_adapt_model_data.py](vision_11_adapt_model_data.py) | **適配模型資料與輸入**：建立 YOLO 資料結構、執行環境與輸入緩衝，改接應用資料。 | 使用者回貼確認四項模型資料接入完成。 [紀錄1](../../firmware/Src/app.c)、[紀錄2](../../docs/engineering-workflow.md) |
| 8、9、10 | [vision_12_integrate_vision_application.py](vision_12_integrate_vision_application.py) | **整合搜尋與顯示應用**：修改 app.c 與 finder.h，接入 YOLO 推論、目標篩選、連續確認及遮罩顯示。 | 後續回貼確認應用與標頭更新，YOLO 推論與遮罩顯示接入。 [紀錄1](../../firmware/Src/app.c)、[紀錄2](../../firmware/Inc/finder.h)、[紀錄3](../../docs/engineering-workflow.md) |
| 6、11 | [vision_13_configure_camera_and_memory.py](vision_13_configure_camera_and_memory.py) | **配置攝影機與記憶體**：修改中央方形輸入、連結記憶體區段與分離映像輸出規則。 | 後續回貼確認 app_cam.c、連結腳本及 Makefile 修改完成。 [紀錄1](../../firmware/Src/app_cam.c)、[紀錄2](../../firmware/Gcc/STM32N657xx.ld)、[紀錄3](../../firmware/Makefile) |
| 11、22 | [vision_14_build_main_vision.py](vision_14_build_main_vision.py) | **建置正式視覺主工程**：建置正式應用、分離視覺指令並封裝部署產物。 | finder_vision_20261004_193031_265404 成功，列出當時四份映像大小與位址；這是加入 KWS 前的視覺階段。 [紀錄1](../../docs/evidence/development-history/vision_image_layout_20261004.txt)、[紀錄2](../../docs/engineering-workflow.md) |
| 22 | [inspect_boot_payload.py](inspect_boot_payload.py) | **檢查開機映像有效載荷**：讀取 ELF 符號、向量與反組譯，逐位元組比較原始程式及封裝內容。 | 後續終端輸出確認內容一致，但原有效載荷位於 0x240。 [紀錄1](../../docs/original-history-review.md)、[紀錄2](../../docs/toolchain-compatibility.md) |
| 22 | [realign_and_flash_application.sh](realign_and_flash_application.sh) | **重新對齊封裝與原燒錄流程**：以 -align 重新封裝，核對 0x400 與完整內容，備份並替換舊映像，再接續寫入。 | 對齊與內容檢查通過；當次在唯讀檔案替換提示中斷，後續由下一份流程完成替換。 [紀錄1](../../docs/original-history-review.md)、[紀錄2](../../docs/toolchain-compatibility.md) |
| 22 | [retry_aligned_application_flash.sh](retry_aligned_application_flash.sh) | **接續替換對齊映像並燒錄**：重新核對 0x400 與內容，用 mv -f 替換唯讀映像後直接寫入應用程式。 | 下一輪回貼出現 KWS 運行輸出；該輪沒有獨立完整燒錄日誌，與後來定版寫入日誌分列。 [紀錄1](../../docs/original-history-review.md)、[紀錄2](../../docs/toolchain-compatibility.md) |
| 23 | [export_fixed_reference.py](export_fixed_reference.py) | **匯出固定五類參考**：讀取當時模型與係數；保存五段 PCM、637 個 INT8 特徵及電腦輸出。 | 原對話回報參考資料已保存；固定參考 JSON 已公開。 [紀錄1](../../docs/evidence/development-history/fixed_reference_20261007.json) |
| 23 | [install_fixed_comparison.py](install_fixed_comparison.py) | **接入固定 INPUT／PCM 比對**：修改當時 finder_kws.c 與比較標頭，安裝兩條板端比對路徑。 | 對應固定五類比較流程；重設後取得兩條路徑的實際 CMP 輸出。 [紀錄1](../../docs/original-history-review.md)、[紀錄2](../../firmware/Src/finder_kws.c) |
| 22、23 | [build_flash_fixed_comparison.py](build_flash_fixed_comparison.py) | **建置與寫入固定比較版**：建置、分離映像、封裝並直接寫入應用程式。 | 對應固定比較版的建置／寫入步驟；比較結果與工具動作分別保存。 [紀錄1](../../docs/original-history-review.md) |
| 20、24、25 | [install_live_comparison.py](install_live_comparison.py) | **接入即時資料比對**：修改當時韌體，加入即時資料回傳與語音接受診斷設定。 | 接入後的四例資料呈現數值一致性與安靜誤判，供後續資料迭代。 [紀錄1](../../docs/evidence/development-history/live_comparison_20261007.json) |
| 22、24 | [build_flash_live_comparison.py](build_flash_live_comparison.py) | **建置與寫入即時比較版**：建置、封裝、核對既有權重與視覺指令，再直接寫入應用程式。 | 對應即時四例比較的韌體部署流程。 [紀錄1](../../docs/original-history-review.md)、[紀錄2](../../docs/evidence/development-history/live_comparison_20261007.json) |
| 23、24 | [compare_live_windows.py](compare_live_windows.py) | **接收與重算即時四例**：開啟串列埠，收取 PCM／特徵／輸出，核對長度與 CRC32，重算電腦兩條路徑並保存結果。 | 四例 INT8 特徵差異皆為 0；輸出最大差異依序為 0、0、3、1。 [紀錄1](../../docs/evidence/development-history/live_comparison_20261007.json)、[紀錄2](../../docs/evidence/development-history/live_serial_events_20261007.log) |
| 24、25 | [record_voice_diagnostics.py](record_voice_diagnostics.py) | **錄製帶標籤的語音診斷**：開啟串列埠，以時段提示錄製六次口令，整理分數、命中及削波資訊。 | 開發歷程保留六次僅接受兩次的診斷，後續擴充現場資料。 [紀錄1](../../docs/original-history-review.md) |
| 26 | [prepare_live_collection.py](prepare_live_collection.py) | **準備 48 段收集模式**：建立收集計畫並修改當時韌體的擷取排程／旗標。 | 後續收集完成 48 段，32 段開發、16 段保留。 [紀錄1](../../kws/live_collection_plan.json)、[紀錄2](../../docs/evidence/development-history/live_dataset_manifest_20261008.json) |
| 22、26 | [build_flash_live_collection.py](build_flash_live_collection.py) | **建置與寫入收集版**：建置及封裝收集韌體，保存計畫，並直接寫入應用程式。 | 對應 48 段現場收集前的板端部署流程。 [紀錄1](../../docs/evidence/development-history/live_dataset_manifest_20261008.json)、[紀錄2](../../docs/original-history-review.md) |
| 26 | [collect_live_dataset.py](collect_live_dataset.py) | **接收 48 段現場資料**：依計畫提示發音；接收串列封包、核對 CRC32、保存 WAV、用途與雜湊清單。 | 原對話有逐段保存與收集完成回報，公開清單保留 48 段結果。 [紀錄1](../../docs/evidence/development-history/live_dataset_manifest_20261008.json) |
| 26、27 | [check_live_dataset.py](check_live_dataset.py) | **檢查收集資料與訓練接法**：讀取既有清單、PCM 雜湊、類別／用途計數與訓練程式標記。 | 對應從現場收集轉入重訓前的資料檢查；原始檔與清單分別保存。 [紀錄1](../../docs/evidence/development-history/live_dataset_manifest_20261008.json)、[紀錄2](../../kws/training_snapshot/train_kws_groupcv.py) |
| 17、28 | [generate_groupcv_model.py](generate_groupcv_model.py) | **定版 KWS 產碼**：複製候選模型、係數與設定，執行 ST Edge AI；接著以遞迴搜尋檢查產物。 | 產碼本身完成；原檢查因正式輸出與工具工作目錄同名檔重複而中止，後續由下一份程式核對。 [紀錄1](../../docs/evidence/development-history/codegen_20261008/codegen.log)、[紀錄2](../../docs/evidence/development-history/codegen_20261008/command.json)、[紀錄3](../../docs/original-history-review.md) |
| 17、28 | [inspect_groupcv_codegen.py](inspect_groupcv_codegen.py) | **限定正式產碼目錄核對**：限定 st_ai_output，核對既有產物、模型雜湊與版本。 | 修正前一步的檔案搜尋範圍；既有 Neural-ART 產碼結果有效。 [紀錄1](../../docs/evidence/development-history/codegen_20261008/kws_network_generate_report.txt)、[紀錄2](../../docs/original-history-review.md) |
| 17、22、28、29 | [install_build_groupcv.py](install_build_groupcv.py) | **同步定版產物並建置封裝**：備份並替換模型、係數與量化參數，關閉比較／收集，建置並以對齊選項封裝，產生映像清單。 | 對應已公開的定版建置日誌與映像清單；輸入零點更新為 7。 [紀錄1](../../docs/evidence/development-history/deployment_20261008/build.log)、[紀錄2](../../docs/evidence/development-history/deployment_20261008/flash_manifest.json) |
| 29 | [flash_groupcv.py](flash_groupcv.py) | **寫入定版應用與 KWS 權重**：核對雜湊及封裝標頭，直接寫入兩份映像、驗證並更新版本指標。 | 應用與 KWS 權重均有寫入驗證成功日誌；其餘三份映像沿用既有內容。 [紀錄1](../../docs/evidence/development-history/deployment_20261008/flash_verified.json)、[紀錄2](../../docs/evidence/development-history/deployment_20261008/flash_finder_signed.bin.log)、[紀錄3](../../docs/evidence/development-history/deployment_20261008/flash_kws_weights.bin.log) |
| 30 | [record_voice_groupcv.py](record_voice_groupcv.py) | **錄製定版語音操作**：開啟串列埠，依標籤提示操作並保存語音接受與搜尋目標紀錄。 | 三種命令各兩次正確接受；該輪視覺紀錄為 found=0，影片另呈現整合展示。 [紀錄1](../../docs/evidence/development-history/voice_groupcv_20261008.log)、[紀錄2](../../docs/results.md) |

## 產碼檢查的前後版本

`generate_groupcv_model.py` 保存原先的遞迴產物搜尋：ST Edge AI 已完成產碼，但同名檔案同時存在於正式輸出與工具工作目錄，原檢查因此停止。`inspect_groupcv_codegen.py` 是後續將搜尋限定在正式 `st_ai_output` 的核對流程；`install_build_groupcv.py` 再使用該組產物。此處保留實際演進，沒有把原檢查改寫成另一個版本。

## 公開時的調整與環境

原程式本文保留；僅將裝置專屬身分改由環境變數取得，Python 必要時補上 `import os`：

| 環境變數 | 使用處 |
| --- | --- |
| `N6_SERIAL_PORT` | 即時比較、收集與語音紀錄程式所開啟的串列裝置路徑 |
| `N6_PROBE_SERIAL` | 燒錄程式傳給 STM32CubeProgrammer 的 ST-LINK 選擇參數 |

程式保留 `$HOME/STM32N6ai/course17_voice_object_finder`、當時工具安裝位置與歷史產物指標；TensorFlow／NumPy 等相依與原啟動直譯器記於來源表。參考模型、前處理係數及錄音等外部產物需與各步驟版本配對。

[來源與雜湊](source-provenance.json)逐檔記錄原對話節點、程式區塊位置、原始區塊／抽出本文／公開版 SHA-256、公開調整及對應結果。這次整理只做原碼比對、語法解析與去識別檢查，未重新執行程式、產碼、訓練或燒錄。完整階段對照見[32 步來源映射](../../docs/development-source-map.json)。
