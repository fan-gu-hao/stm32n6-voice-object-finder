# 系統架構

[繁體中文](architecture.md) | [English](architecture.en.md)

以下依本機定版紀錄整理；表中的模型、輸出與紀錄路徑描述完整本機專案，不代表全部包含於公開儲存庫。


| 路徑 | 角色 |
| --- | --- |
| `firmware/Src/main.c` | 時脈、NPU、快取、外部 RAM／Flash、UART 與 FreeRTOS 初始化 |
| `firmware/Src/app.c` | KWS 命令接受、目標選擇、YOLO 推論、顯示與工作排程 |
| `firmware/Src/finder_mic.c` | MDF1＋GPDMA 收音、環形緩衝、一秒 PCM 快照 |
| `firmware/Src/finder_kws.c` | CPU MFCC 前處理、量化、STAI KWS 推論 |
| `firmware/Inc/finder_kws_tables.h` | 與目前 KWS 模型搭配的前處理係數及量化參數 |
| `firmware/Src/app_cam.c` | 官方 Camera Middleware／DCMIPP 顯示管線及模型輸入管線 |
| `firmware/Model/`、`firmware/Model/kws/st_ai_output/` | 目前編入韌體的視覺及 KWS 產碼 |
| `firmware/Lib/AI_Runtime/` | 官方 STAI／ATON 執行環境及 CPU 軟體算子 |
| `firmware/Lib/ai-postprocessing-wrapper/`、`firmware/Lib/lib_vision_models_pp/` | 官方 YOLOv8 實例分割後處理 |
| `firmware/Makefile`、`firmware/mks/`、`firmware/Gcc/STM32N657xx.ld` | 實際 GCC 建置入口與記憶體配置 |
| `vision/` | 官方實例分割範例、視覺模型與產碼來源；保留既有修改與歷史 |
| `kws/` | 既有收音、資料整理、訓練程式、資料、模型及評估報告 |
| `output/`、`logs/` | 歷次輸出與既有測試紀錄，並非每個歷史輸出都是定版 |

MDF 以名目 16 kHz 取一秒、16,000 點音訊，約每 200 ms 提供新視窗；歷史板上紀錄回報約 16,009 Hz。MFCC 流程為去平均值、480 點週期 Hann 窗、320 點位移、512 點 FFT、40 個 HTK Mel 濾波器、自然對數、13 維正交 DCT，再依模型係數標準化、截限至 ±6 並量化成 `49×13×1 int8`。輸出順序為 cup、bottle、phone、unknown、silence。

KWS 使用深度可分離 CNN，NPU 與 CPU 混合執行，最後 Softmax 為 CPU 算子。輸入寫入前保留既有 NPU／CPU 快取一致性處理。命令接受條件為峰值至少 2500、最高分至少 0.90、領先次高分至少 0.25、連續兩窗命中及命令間隔至少 1200 ms；接受後經兩個安靜視窗重新啟用。

攝影機 Pipe 1 提供 LCD 影像，Pipe 2 取中央正方形、縮放成 `256×256 RGB uint8`。YOLO 有兩組 int8 輸出：`116×1344` 偵測資料及 `64×64×32` mask prototypes。官方後處理依 tensor 大小辨識輸出順序，執行解碼、NMS 與遮罩生成；信心門檻 0.50、NMS IoU 0.40、最多 10 個結果。應用程式篩選 COCO cup=41、bottle=39、cell phone=67，連續兩幀且框 IoU 至少 0.30 才顯示 FOUND。

單一 `nn_thread_fct()` 依序輪詢 KWS、執行 YOLO，共用 NPU；沒有同時執行兩個模型。語音切換搜尋目標，YOLO 持續執行。另有 LCD 顯示工作與 ISP 更新工作。UART 為 115200、8N1。

| 記憶體區域 | 起點／容量 | 既有成功建置的用量 |
| --- | --- | ---: |
| 應用 SRAM | `0x34000400`／1023 KiB | 535,544 bytes |
| 視覺指令 Flash | `0x71380000`／2 MiB | 230,528 bytes |
| 應用與顯示 PSRAM | `0x91000000`／16,128 KiB | 8,949,920 bytes |
| KWS 專用 RAM | `0x91FC0000`／256 KiB | 產碼配置約 17.03 KiB |

KWS 專用 RAM 使用產碼中的絕對位址，linker 顯示 0 B 不表示沒有使用。YOLO activation pool 也由產碼配置，不能只看 linker 報表。
