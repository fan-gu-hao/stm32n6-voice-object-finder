# 雙模型記憶體配置與部署

[繁體中文](memory-deployment.md) | [English](memory-deployment.en.md)

本專案將 **CPU 應用、YOLO 工作區、KWS 工作區、影像顯示緩衝、模型權重與 NPU 執行指令**分別配置，再協調模型產碼、韌體連結與燒錄位址。兩個模型共用一個 NPU，於同一推論工作依序執行；各自保留模型上下文及輸入輸出，配合 CPU／DMA／NPU 的快取交接。

以下位址區間均為「包含起點、不包含終點」。KiB = 1,024 位元組，MiB = 1,048,576 位元組；**保留容量、連結器區段用量、模型產碼配置量與映像檔大小是不同統計**。

## 三個配置層共同決定部署結果

| 配置層 | 負責內容 | 本專案的實作 |
| --- | --- | --- |
| 模型記憶體池（memory pool，`.mpool`） | 模型編譯器可配置的權重、活化值與輸入輸出區域，以及存取屬性 | 視覺模型池來源固定並另存上游參考；[KWS 模型池](../kws/deployment/kws.mpool)另指定語音 RAM 與 Flash |
| 韌體連結腳本（linker script）與區段屬性 | CPU 程式、共用執行環境、全域資料、堆疊、顯示緩衝與視覺指令 | [連結腳本](../firmware/Gcc/STM32N657xx.ld)搭配[建置巨集與映像輸出規則](../firmware/Makefile) |
| 映像封裝與燒錄配置 | 實際寫入 Flash 的映像、位址、標頭與內容 | 應用映像、兩組模型權重、視覺指令及 FSBL；[定版寫入清單](evidence/development-history/deployment_20261008/flash_manifest.json) |

模型池描述編譯器的配置範圍，不等於整個韌體的配置，也不等於整個範圍已被使用。CPU 執行位置與開機映像儲存位置也要分開：本案主應用映像寫入 `0x70100000`，應用程式則連結在 `0x34000400` 起的內部 SRAM 執行。

## 執行期間：應用、兩模型與顯示的 RAM 分工

| 用途 | 位址／配置範圍 | 保留容量 | 已保存的配置或用量 |
| --- | --- | ---: | --- |
| 主應用、FreeRTOS、周邊驅動、共用 AI 執行環境、模型 CPU 控制程式及一般資料 | `0x34000400–0x34100000` | 1,023 KiB | 定版連結器用量 **535,544 B** |
| 麥克風 DMA／環形緩衝、CPU 前處理工作區與模型上下文 | 同上，使用一般靜態資料區 | 包含在上述應用 SRAM | 音訊環形緩衝為 32,768 個 16 位元樣本；MFCC 工作區使用靜態陣列，與模型活化值分開 |
| YOLO 內部工作區 | 視覺模型池自 `0x34100000` 起的內部 SRAM／NPU RAM | 依各模型池配置，詳見下表 | 實際各池用量需對應本版視覺產碼報告 |
| YOLO 外部工作區池 | `0x90000000–0x91000000` | 上游模型池提供 16 MiB | 這是可配置容量，不能直接當成模型用量 |
| 相機輸入、LCD 畫面、後處理與遮罩快照 | `0x91000000–0x91FC0000` | 16,128 KiB（15.75 MiB） | 定版 `.psram_section` 用量 **8,949,920 B** |
| KWS 活化值，包含模型輸入輸出 | `0x91FC0000–0x92000000` | 256 KiB | 定版模型配置 **17,440 B**；使用包絡範圍至 `0x91FC4420` |

應用與顯示數字來自[定版建置日誌](evidence/development-history/deployment_20261008/build.log)；KWS 數字來自[定版產碼報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)。它們不是全系統執行期間的動態記憶體峰值。

連結器會將 `KWS_RAM` 顯示為 **0 B**，因為模型產碼另以絕對位址使用該區，沒有一般連結區段占入；模型報告記錄的 17,440 B 才是這次 KWS 活化值配置。**不能把連結器的 0 解讀成語音模型不使用 RAM。**

### 視覺模型的上游可配置池

與本案固定視覺來源對應的[上游模型池](https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Model/my_mpools/stm32n6-app2_STM32N6570-DK.mpool)列出以下區域。這張表呈現編譯器配置，不以其他視覺專案的量測代替本案用量。

| 池名 | 起點 | 配置容量 |
| --- | --- | ---: |
| `cpuRAM2` | `0x34100000` | 1,024 KiB |
| `npuRAM3` | `0x34200000` | 448 KiB |
| `npuRAM4` | `0x34270000` | 448 KiB |
| `npuRAM5` | `0x342E0000` | 448 KiB |
| `npuRAM6` | `0x34350000` | 448 KiB |
| `hyperRAM` | `0x90000000` | 16 MiB |

同一配置中的 `flexMEM` 與 `cpuRAM1` 容量設為 0；正式應用連結器則將 CPU 應用限制在 `0x34100000` 之前。兩者配合，避免一般程式與資料向後占用視覺模型需要的區域。

## 儲存與開機：五份映像的分工

| 映像／資料 | Flash 儲存位置 | 容量或已保存大小 | 執行時用途 |
| --- | --- | --- | --- |
| 第一階段開機載入程式（FSBL），`ai_fsbl.hex` | 依 HEX 記錄內含位址 | 地址範圍以實際 HEX 解析為準 | 初始化開機所需環境並載入應用 |
| 主應用映像，`finder_signed.bin` | `0x70100000` 起 | 依該次封裝產物核對 | CPU 程式連結至內部 SRAM；共用執行環境與兩模型的 CPU 控制程式包含其中 |
| 視覺權重，`vision_weights.bin` | `0x70380000` 起 | 原始開發輸出記錄 **3,474,865 B** | YOLO 權重 |
| 語音權重，`kws_weights.bin` | `0x70700000–0x70710000` | 保留 64 KiB；模型報告權重配置 **11,409 B** | KWS 權重 |
| 視覺執行指令，`vision_commands.bin` | `0x71380000–0x71580000` | 保留 2 MiB；連結器區段 **230,528 B** | YOLO 執行階段控制器指令（EC blob） |

五份映像共同組成雙模型部署。KWS 本版沒有獨立 EC blob：官方工具產生的 C 控制程式連入主應用，CPU 執行控制流程，NPU 執行 11 個硬體階段，最後一個 Softmax 階段由 CPU 執行。

`finder_signed.bin` 是既有檔名；本案使用無金鑰模式（`-nk`）加入開機標頭，不將它描述成密碼學簽章。FSBL 的 Flash 位址由 HEX 內含記錄決定，不能從連結腳本中的 `_fsbl_start_address = 0x34180000` 推導；後者是 RAM 位址。

### 視覺權重池與 KWS 權重的邊界

上游視覺 `octoFlash` 模型池提供 `0x70380000–0x71380000`，共 16 MiB。**這個可配置範圍包含後來選定的 KWS 權重位置 `0x70700000`**，所以不能只根據兩個池名稱不同，就宣稱整個池互不重疊。

原始開發輸出所記錄的視覺權重為 3,474,865 B，對應實際內容區間：

| 已記錄產物 | 內容起點 | 內容終點，不含 | 與下一區域的關係 |
| --- | --- | --- | --- |
| 視覺權重 | `0x70380000` | `0x706D05B1` | 到 KWS 起點尚有 **195,151 B** |
| KWS 權重保留區 | `0x70700000` | `0x70710000` | 64 KiB 獨立保留配置 |

視覺大小取自正式視覺主工程在 2026-10-04 的[使用者終端輸出節錄](evidence/development-history/vision_image_layout_20261004.txt)，其中記錄權重與指令的長度、位址；該輪應用大小屬尚未加入 KWS 的視覺階段。開發過程與版本對照見[原始歷程覆核](original-history-review.md)。這裡依記錄計算邊界，沒有宣稱本次重新讀取了未公開的二進位權重。

目前記錄的內容邊界落在 KWS 之前。**更換或重新產生視覺模型後，必須重新核對**權重起點加檔案長度、產碼報告的使用範圍及燒錄區域；不能以原有 16 MiB 池容量作為雙模型工程的可用權重上限。若越過 `0x70700000`，應一致調整模型池、權重位置與部署清單，再重新產碼及建置。

## 從官方底座到本案配置的調整

| 比較項目 | 固定官方來源 | 本案整合處理 |
| --- | --- | --- |
| CPU 應用 SRAM | 手部範例 `6c313001…` 保留 1,535 KiB；實例分割範例 `42f7d645…` 保留 1,023 KiB | 將正式手部底座改為 1,023 KiB，對齊視覺模型工作區邊界 |
| 視覺執行指令 | 實例分割連結腳本已有 `0x71380000`／2 MiB 的 `.flash_section` | 將此配置接入正式底座，搭配區段巨集把產碼的 `.flash_blob` 納入該區 |
| PSRAM 未初始化緩衝 | 官方手部及分割範例原本均有 `.psram_section (NOLOAD)` | 沿用此機制，接入本案的顯示、相機、後處理及遮罩快照 |
| KWS 專用 RAM | 手部底座原有 16 MiB 一般 PSRAM | 一般區縮為 15.75 MiB，尾端 256 KiB 列為 `KWS_RAM`，並在 KWS 模型池指定相同位址 |
| 映像輸出 | 產碼指令與 CPU 程式落在不同位址區段 | 從同一 ELF 分別抽取主應用與視覺指令，避免位址空洞造成映像膨脹 |

官方對照：[手部範例連結腳本](https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks/blob/6c313001f69d3ddb1ffa7bd700aba74f9c11037b/Gcc/STM32N657xx.ld)、[實例分割連結腳本](https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation/blob/42f7d645f1ed61967a922defa4aa97b95d390b16/Application/STM32N6570-DK/STM32CubeIDE/STM32N657xx.ld)。這些是跨範例移植與加入第二個模型時完成的適配；原始範例配置各自服務其原有模型。

## 區段、快取與資料生命週期

`NOLOAD` 讓 PSRAM 工作緩衝不以初始化內容塞入燒錄映像；必要的畫面緩衝由應用明確初始化。KWS 模型工作區另由產碼配置，與一般 PSRAM 區隔。

| 資料交接 | 程式中的處理 |
| --- | --- |
| 攝影機 → CPU → YOLO | 取得相機緩衝、使 CPU 舊快取失效，複製到模型輸入，完成快取維護後才歸還相機緩衝 |
| 麥克風 DMA → CPU | DMA 描述節點對齊 64 B、音訊緩衝對齊 32 B；回呼處理快取後寫入環形緩衝，以記憶體屏障發布位置 |
| CPU 特徵 → KWS NPU | 寫入新輸入前先處理 NPU 64 B 快取列與 CPU 舊副本；寫入後清理 CPU 快取，才開始推論 |
| KWS 最後輸出 → CPU | 最後 Softmax 在 CPU 執行，讀取 CPU 寫出的量化結果 |
| 後處理 → 顯示工作 | 先保存結果與遮罩快照；顯示工作鎖內複製、鎖外繪圖，避免下一輪推論覆寫使用中的資料 |

實作來源：[系統與影像交接](../firmware/Src/app.c)、[連續收音](../firmware/Src/finder_mic.c)、[特徵與模型快取交接](../firmware/Src/finder_kws.c)。共享 NPU 由單一推論工作依序使用；兩模型的靜態工作區與顯示資料仍分開管理。

## 建置與部署證據

- [定版連結結果](evidence/development-history/deployment_20261008/build.log)：應用 SRAM、視覺指令及 PSRAM 區段用量。
- [KWS 產碼報告](evidence/development-history/codegen_20261008/kws_network_generate_report.txt)：模型池、使用範圍、權重、活化值及硬體／軟體階段。
- [定版映像清單](evidence/development-history/deployment_20261008/flash_manifest.json)與[寫入驗證結果](evidence/development-history/deployment_20261008/flash_verified.json)：應用及 KWS 權重的位址、雜湊與成功驗證。
- [原始開發歷程](original-history-review.md)：視覺產碼、框架移植、封裝有效載荷 `0x240 → 0x400` 的修正及實際運行紀錄。
- [建置與版本相容性](build.md)：工具、官方範例執行期配對與既有建置入口。

定版更新直接保存了應用與 KWS 權重兩份映像的成功寫入紀錄，其餘三份沿用既有內容；這些記錄與最後板端操作共同支持整合版本已實際部署運行。展示影片及獨立供電／冷啟動的完成狀態另見[結果與版本範圍](results.md)。
