# CubeIDE 來源目錄同步工具

[sync_cubeide_sources.py](sync_cubeide_sources.py)為原專案已使用的工具，原樣保存，SHA-256 為 `fa385d29546b60dfc4faf946492245af6ccb012889ae893afc7ba8ff8ffb934c`。

它把分散的來源連結整合為 `Src`／`Inc` 資料夾連結，讓新增來源和標頭可隨 IDE 重新整理顯示。這項操作處理 Eclipse 的來源瀏覽設定；實際編譯清單仍由 [Makefile](../../firmware/Makefile)及其建置片段決定。

| 實作 | 用途 |
| --- | --- |
| 解析既有位置 | 處理專案相對路徑、父層路徑、本機檔案 URI 與絕對路徑；遇到不相符或遠端連結即停止 |
| 預覽與重複執行 | 預設只列出修改；已完成資料夾連結時不再寫入 |
| 備份與併發檢查 | 寫入前備份，前後核對原設定雜湊，避免蓋掉 IDE 同時產生的變更 |
| 原子替換 | 暫存檔寫完後同步至磁碟，保留權限，再以原子替換更新設定 |

在本公開儲存庫根目錄檢視時，應明確指定根目錄；此命令只預覽：

```bash
python3 tools/ide/sync_cubeide_sources.py --root "$PWD"
```

原工具預設位置仍為家目錄下的 `STM32N6ai/course17_voice_object_finder`。`--apply` 會修改指定專案的設定，使用前需關閉 IDE；本次公開整理沒有執行套用。雙模型定版韌體的 C／H 與編譯行為未因本工具的封存而更動。
