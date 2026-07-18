# 火箭地面站系統重構優化與修復結果 (Walkthrough)

本文件總結了本次針對地面站系統 (`rocket_system_ground_side`) 進行的架構優化與穩定性修復工作。

---

## 1. 變更內容說明 (Changes Made)

### 1.1 核心與通訊層 (`src/core`)
- **[communicator.py](file:///d:/Document_J/code/rocket_system_ground_side/src/core/communicator.py)**：
  - 引進 `threading.Event()` (命名為 `self.stop_event`) 用於重連時的無延遲等待與退出喚醒。
  - 重構 `_read_serial`，改用阻塞式的 `readline()`，簡化了原本輪詢 `in_waiting` 的繁重邏輯。
  - 修正了原本捕獲 `FileNotFoundError` 後會直接 `break` 重試迴圈，導致外層 read 迴圈不斷發起 reconnect 造成 100% CPU 佔用的邏輯鎖死問題。
  - 修改 `_process_data` 中的解碼方式，加入 `errors='ignore'` 以避免通訊雜訊產生的亂碼引發 `UnicodeDecodeError` 異常。

### 1.2 儲存層 (`src/storage`)
- **[json_storage.py](file:///d:/Document_J/code/rocket_system_ground_side/src/storage/json_storage.py)**：已刪除。
- **[storage_observer.py](file:///d:/Document_J/code/rocket_system_ground_side/src/storage/storage_observer.py)**：
  - 移除了對 JSON 儲存與 `LogData` 分支的調用，依據使用者指令，**僅保留 CsvDataStorage 寫入 CSV 檔案**。
  - 簡化了結構，使遙測資料直接轉發至 CSV 追加儲存，完全解決了頻繁讀寫整個 JSON 檔造成的嚴重磁碟 I/O 阻塞。

### 1.3 GUI 與可視化層 (`src/gui`)
- **[log_displayer.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/visualizers/log_displayer.py)**：
  - 建立 `LogSignalEmitter(QObject)` 與自定義 Qt 訊號 `log_received = pyqtSignal(str)`。
  - 將背景日誌輸出與 stdout 重定向，統一透過該訊號將日誌傳回 PyQt 的 GUI 主線程進行 `append` 更新，**徹底修復了非主線程更新 UI 組件導致的崩潰隱憂**。
- **[location_displayer.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/visualizers/location_displayer.py)**：
  - 改用單次 Leaflet.js HTML 內容載入。
  - 更新座標時利用 `runJavaScript("updateMarker(lat, lng)")` 更新地圖視角與紅點標記位置，**解決了重複渲染地圖 HTML 導致的閃屏與效能瓶頸**。
- **[visualization_tools.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/visualizers/visualization_tools.py)**：
  - 清理並刪除了重複定義的 `quaternion_multiply` 函數。

---

## 2. 測試與驗證過程 (Verification)

### 2.1 語法與編譯檢查
- 運行 `python -m py_compile` 對所有修改的 Python 檔案進行了編譯，全部順利通過無語法與導入錯誤。

### 2.2 遙測重連與關閉響應測試
- 使用虛擬環境中的 Python 運行 `main.py`。
- **重連檢驗**：由於無 COM3 硬體連接，系統成功捕獲 `FileNotFoundError` 錯誤，並順利進入每 5 秒一次的重試機制。CPU 單核佔用率幾乎為 0%，不再出現空轉鎖死。
- **即時退出檢驗**：在等待重連期間，直接點擊關閉 GUI 視窗，背景通訊線程能瞬間響應 Event 被喚醒，程式立即退出，無延遲與阻塞現象。
