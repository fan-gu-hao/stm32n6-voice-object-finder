# 收音與串列傳輸工具

[繁體中文](README.md) | [English](README.en.md)

這兩支主機工具來自既有 `course15_n6_mic_test` 專案。公開副本調整專案路徑、偵錯器序號與串列埠設定；收音協定、CRC32 檢查及 GDB 載入流程保留。

| 程式 | 閱讀重點 |
| --- | --- |
| [n6_receive_wav.py](n6_receive_wav.py) | 串列埠獨占、交握、分段接收、逾時處理、CRC32 與 WAV 儲存 |
| [n6_mic_start_and_record.sh](n6_mic_start_and_record.sh) | 工具搜尋、向量表檢查、RAM 載入、核心暫存器設定、啟動檢查點與程序清理 |

## 外部依賴

對應的 [FSBL 原始碼、IDE 設定與上游差異](../recording_firmware/README.md)已公開。主機工具仍需既有收音專案的兩份對應預建韌體；完整 STM32CubeN6 SDK 與下列 ELF／BIN 未隨附：

- `STM32CubeN6/Projects/STM32N6570-DK/Examples/MDF/MDF_AudioRecorder/STM32CubeIDE/FSBL/Debug/MDF_AudioRecorder_FSBL.elf`
- 同目錄的 `MDF_AudioRecorder_FSBL.bin`

這是支援 `N6MIC_READY,1,16000,1,16,80000` 協定的五秒錄音版本，不是任意版本的官方錄音範例。主機工具使用 STM32CubeIDE 2.2.0 的偵錯工具及 Linux 串列埠介面。

## 設定與執行

| 環境變數 | 用途 |
| --- | --- |
| `N6_MIC_ROOT` | 收音專案根目錄；預設為使用者家目錄下的 `STM32N6ai/course15_n6_mic_test` |
| `N6_MIC_IDE` | CubeIDE 安裝位置；預設 `/opt/st/stm32cubeide_2.2.0` |
| `N6_STLINK_SERIAL` | 實際 ST-LINK 偵錯器序號，必填 |
| `N6_MIC_PORT` | 實際 `/dev/serial/by-id/` 串列埠路徑，必填 |

設定完成且板子處於工具要求的開發啟動狀態後，在本儲存庫根目錄執行：

    python3 kws/collect_n6.py

首次錄音會經 GDB 將錄音程式載入 RAM 並啟動，之後接收音訊。這不是目前雙模型展示韌體的啟動指令，會改變板子當下執行的程式。

接收格式為 16 kHz、單聲道、16 位元、80,000 點；串列速率為 115200。原始 WAV 存在收音專案的 `recordings/`，分類後資料位於本儲存庫 `kws/data_raw/`，均不納入公開提交。

本次只做來源碼整理與語法檢查，沒有重新連板錄音。訓練腳本另使用 NumPy、SciPy、scikit-learn 與 TensorFlow；公開版本尚未提供完整的訓練環境版本鎖定檔。
