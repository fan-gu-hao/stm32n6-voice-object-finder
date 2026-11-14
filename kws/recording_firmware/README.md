# 獨立錄音韌體：資料蒐集階段的原始實作

[繁體中文](README.md) | [English](README.en.md)

這是 `course15_n6_mic_test` 已使用的五秒錄音版本，後續供關鍵字辨識資料蒐集使用。保存的 C／H、啟動碼與專案設定均直接來自本機原檔，內容雜湊見[補充來源紀錄](../../docs/evidence/development-history/source_provenance.json)。

## 基底與修改

基底為 [STM32CubeN6](https://github.com/STMicroelectronics/STM32CubeN6/tree/1fc803683e03b0ce78e64523441d31acd0db2829) 的 `Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder`，本機 Git 基準提交為 `1fc803683e03b0ce78e64523441d31acd0db2829`。

官方範例原本將 MDF 錄音經 SAI／WM8904 播放。本版本保留 MDF 與 DMA 初始化，改為先把樣本收進 RAM，再由主迴圈傳至電腦；目前 `main()` 沒有呼叫仍保留在檔內的 `Playback_Init()`。本版實際收音路徑是板上數位麥克風經 MDF，不能僅因專案仍帶有 WM8904 程式就把它當成錄音輸入路徑。

[原始修改差異](upstream_changes.patch)記錄以下變更：啟用 BSP COM、啟用 HAL UART、替換主迴圈與 MDF 回呼，以及將 UART 驅動加入 IDE 專案。

| 程式入口 | 實作內容 |
| --- | --- |
| [main.c](FSBL/Src/main.c) 的 `MicRecord` | 名目 16 kHz、單聲道、16 位元、80,000 點；先錄滿五秒，再傳送 160,000 位元組 |
| `MicCopy` 與 MDF 半滿／全滿回呼 | 2,048 點 DMA 雙半緩衝，每次複製最多 1,024 點；略過前兩個區塊暖機，最後一塊依剩餘長度複製 |
| `MicActive`／`MicFailed`／`MicCount` | 中斷與主迴圈共享錄音狀態；以記憶體屏障發布已完成樣本，主迴圈停止 DMA |
| `MicRecord`／`HAL_MDF_ErrorCallback` | 12 秒擷取逾時、啟停錯誤、樣本不足檢查；飽和交由接收端統計，其他 MDF／DMA 錯誤中止錄音 |
| `MicTx`／`MicCrc32` | 主迴圈分段串列傳輸、長度與 CRC32；中斷回呼不傳送串列資料 |
| `main` | `?` 查詢就緒、`R` 啟動錄音；綠燈表示錄音期間，錯誤以紅燈與協定回報 |
| [stm32n6xx_hal_msp.c](FSBL/Src/stm32n6xx_hal_msp.c)／[中斷入口](FSBL/Src/stm32n6xx_it.c) | MDF 腳位、時脈、GPDMA 鏈結與中斷的官方基礎設定 |
| `MPU_Config`／[連結設定](STM32CubeIDE/FSBL/STM32N657X0HXQ_AXISRAM2_fsbl.ld) | 將 DMA 相關緩衝安排在不可快取區域；這與後來雙模型韌體的快取維護方式分別保存 |

## 傳輸協定與後續整合

就緒訊息為 `N6MIC_READY,1,16000,1,16,80000`。錄音完成後依序傳送 `N6MIC_DATA` 格式／長度／CRC32 標頭、PCM 位元組與 `N6MIC_DONE` 結尾。[主機接收工具](../recording_tools/n6_receive_wav.py)檢查這些欄位、完整長度和 CRC32，再建立 WAV；[收集程式](../collect_n6.py)將錄音安排至五個類別。

此階段是「先錄完再傳送」；雙模型版的[連續收音模組](../../firmware/Src/finder_mic.c)則使用循環 DMA、環形緩衝與一秒滑動視窗。兩個階段各自保存實作，不把後期驅動的參數套回本快照。

## 快照與建置相依

本目錄保存 FSBL 來源、CubeIDE 專案、啟動碼、連結設定與原始 `.ioc`，不是完整 STM32CubeN6 SDK。HAL、BSP、CMSIS 與其他相依仍須來自上述固定基底。IDE 專案保留原環境的來源連結，其中兩個 UART 來源使用本機絕對路徑；移到其他電腦時需對應至該 SDK 的 `Drivers/STM32N6xx_HAL_Driver/Src/`。

`.ioc` 與 [UPSTREAM_README.md](UPSTREAM_README.md)保留官方原貌，描述原始範例；本版本的五秒錄音行為以修改後的 C 程式與差異檔為準，不能僅重新產碼便取代這些修改。原始 ELF／BIN 未收錄。本次僅封存來源，沒有重新建置、連板或驗收。

原始著作權標頭及 [SDK 授權索引](LICENSE.md)保留；索引將範例列為 BSD 3-Clause，其他 SDK 元件各依其條款。
