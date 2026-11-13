# 程式導讀

## 收音與語音前處理

從 [`finder_mic.c`](../firmware/Src/finder_mic.c) 讀取 MDF1、GPDMA 與環形緩衝流程，再讀 [`finder_kws.c`](../firmware/Src/finder_kws.c) 的音訊快照、MFCC、量化與模型呼叫。

[`finder_kws_tables.h`](../firmware/Inc/finder_kws_tables.h) 保存對應模型的前處理係數與量化參數，屬於與模型配套的生成資料。

## 雙模型與找物狀態

[`app.c`](../firmware/Src/app.c) 是整合入口。`nn_thread_fct()` 先輪詢語音辨識，再執行視覺推論；兩模型共用 NPU，沒有同時執行。

閱讀時可追蹤「接受語音命令 → 選擇目標類別 → 篩選視覺結果 → 連續幀確認 → 顯示狀態」。命令接受門檻與連續幀判定屬於應用層；YOLO 解碼、非極大值抑制（NMS）與遮罩計算使用官方後處理。

## 開機、攝影機與記憶體

[`main.c`](../firmware/Src/main.c) 負責時脈、NPU、快取、外部記憶體與作業系統初始化。攝影機管線整合見 [`app_cam.c`](../firmware/Src/app_cam.c)。

對照 [`STM32N657xx.ld`](../firmware/Gcc/STM32N657xx.ld)、[`Makefile`](../firmware/Makefile) 與 [`kws.mk`](../firmware/mks/kws.mk)，可理解應用程式、模型指令、權重與暫存區的配置。部分模型暫存由產碼使用絕對位址配置，不能只以連結器報表判斷全部用量。

## 訓練程式

[`prepare_dataset.py`](../kws/prepare_dataset.py)、[`train_kws.py`](../kws/train_kws.py) 與 [`train_kws_groupcv.py`](../kws/train_kws_groupcv.py) 保留資料整理、訓練及分組驗證的實作。收音入口 [`collect_n6.py`](../kws/collect_n6.py) 使用隨附的 [主機收音工具](../kws/recording_tools/README.md)，並依賴外部收音專案的對應韌體。

## 貢獻範圍

本作品的閱讀重點是收音與語音前處理、訓練流程、雙模型整合、目標選擇與狀態判定，以及記憶體與建置配置。應用程式沿用並修改官方範例框架；保留原有版權聲明。

硬體抽象層（HAL）、板級支援套件（BSP）、FreeRTOS、攝影機中介軟體、STAI／ATON 執行環境及視覺後處理均有上游來源，不能視為本作品從零撰寫的功能。模型產碼與前處理係數也不以手寫程式碼計算貢獻。

## 定版訓練與模型配置

[定版訓練程式快照](../kws/training_snapshot/README.md)可對照實際使用的訓練程式；[KWS 模型產碼配置](../kws/deployment/README.md)保存專用 RAM、Flash 與產碼選項。
