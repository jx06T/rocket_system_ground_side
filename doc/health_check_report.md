# 火箭地面站系統健康檢查報告 (Architecture Health Check Report)

本報告針對火箭地面站系統 (`rocket_system_ground_side`) 的**可維護性 (Maintainability)**與**魯棒性 (Robustness)**進行全面性代碼與架構審查，並提出對應的優化建議與具體改進方案。

---

## 1. 綜合評估 (Executive Summary)

本專案採用了良好的架構設計基礎：
- **職責分離**：藉由觀察者模式 (Observer Pattern) 將數據通訊、數據儲存與 GUI 渲染解耦。
- **異步處理**：通訊端採用雙線程設計（讀取與解析），保障了數據的高頻接收。

然而，在**系統穩定性（魯棒性）**與**效能（高頻 I/O 與渲染）**上存在數個**高風險漏洞**，特別是在多線程 UI 更新、JSON 數據持久化、以及地圖即時渲染等模組，若在高頻率、長時間的遙測數據傳輸下運行，極易導致程式閃退、CPU 佔滿或數據丟失。

---

## 2. 魯棒性與穩定性審查 (Robustness & Stability)

### 🔴 漏洞 2.1：非 GUI 線程直接修改 UI (Critical)
* **相關檔案**：[log_displayer.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/visualizers/log_displayer.py)
* **問題說明**：
  `LogDisplayer` 重定向了系統的 `sys.stdout` / `sys.stderr` 並註冊了 `QtLogHandler` 到 root logger 中。當 `SerialCommunicator` 背景線程調用 `self.logger.info()` 時，日誌處理程序會直接呼叫 `self.text_widget.append(msg)`。
  **在 Qt 框架中，嚴禁從非主線程直接呼叫 GUI 元件方法**。這會導致隨機性的記憶體衝突 (Segmentation Fault)、UI 凍結或程式無預警閃退。
* **改進建議**：
  日誌顯示器應與 `QtGuiObserver` 類似，透過自定義的 `QObject` 和 `pyqtSignal` 將日誌訊息發送到主線程，由主線程的槽函數更新 `QTextEdit`。

---

### 🔴 漏洞 2.2：高頻率 JSON 儲存效能瓶頸與資料損毀風險 (Critical)
* **相關檔案**：[json_storage.py](file:///d:/Document_J/code/rocket_system_ground_side/src/storage/json_storage.py)
* **問題說明**：
  在 `JsonDataStorage.save()` 中，每一次收到遙測數據（通常為 10Hz，即每秒 10 次），程式會：
  1. 讀取並解析**整個 JSON 檔案**到記憶體。
  2. 將新遙測點 append 到 list 中。
  3. 將**整個 list 重新寫回硬碟**。
  
  這會隨著遙測時間增加，檔案體積變大，導致磁碟 I/O 呈指數型上升，造成嚴重卡頓。更危險的是，`open(filename, 'w')` 會先清空檔案，若寫入過程中系統斷電、斷線或閃退，**所有歷史遙測數據將全部損毀消失**。
* **改進建議**：
  1. **避免高頻 JSON 寫入**：遙測數據儲存推薦以 CSV 這種可以 append-only 寫入的格式為主。
  2. **非同步批次寫入**：若必須使用 JSON，應在記憶體中快取 (Buffer) 資料，定期（如每 5 秒或累積 50 筆）才寫入一次，且寫入時先寫入臨時檔再覆蓋，避免寫入中途崩潰導致數據丟失。

---

### 🟡 漏洞 2.3：地圖高頻渲染 CPU 暴漲與畫面閃爍 (Medium)
* **相關檔案**：[location_displayer.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/visualizers/location_displayer.py)
* **問題說明**：
  每當 GPS 座標更新時，`LocationDisplayer.update()` 會調用 `create_map()`，該方法重新建立一個 `folium.Map` 物件，渲染整個 HTML，再調用 `self.web_view.setHtml(html_string)`。
  `setHtml` 會使內嵌的 Chromium 瀏覽器（WebEngine）重新載入整張網頁，這在頻繁更新下會消耗大量 CPU 與記憶體，且地圖畫面會不斷空白閃爍，實用性極低。
* **改進建議**：
  在初始化時加載一次 Folium 地圖，並在 HTML 中植入 JavaScript 更新標記的函數。後續更新經緯度時，透過 `web_view.page().runJavaScript("updateMarker(lat, lng)")` 實現平滑、零負載更新。

---

### 🟡 漏洞 2.4：重連機制中的死循環與退出 Hang 起問題 (Medium)
* **相關檔案**：[communicator.py](file:///d:/Document_J/code/rocket_system_ground_side/src/core/communicator.py)
* **問題說明**：
  1. 在 `_reconnect` 中，如果拋出 `FileNotFoundError`（例如 Windows 找不到該 COM Port），會執行 `break` 退出重連循環。然而，這時 `self.running` 依然為 `True`，所以 `_read_serial` 會立即再次觸發 `_reconnect()`，形成無間斷的快速重試死循環，瞬間耗盡單核 CPU。
  2. 如果重連時處於 `time.sleep(self.retry_interval)` (5秒)，若此時使用者關閉視窗呼叫 `stop()`，`join()` 會被阻塞，導致程式關閉時出現 1~5 秒的延遲。
* **改進建議**：
  1. 移除 `FileNotFoundError` 的 `break`，或在斷開時將狀態設為 Error 並安全暫停。
  2. 在重連的 Sleep 中使用事件 flag（如 `threading.Event().wait(timeout)`）代替 `time.sleep`，這樣當主程序關閉時可立即響應退出。

---

### 🟢 漏洞 2.5：雜訊解碼異常未隔離 (Low)
* **相關檔案**：[communicator.py](file:///d:/Document_J/code/rocket_system_ground_side/src/core/communicator.py)
* **問題說明**：
  `decoded_data = raw_data.decode().strip()` 預設使用 UTF-8 解碼。如果序列埠因電磁干擾或連線不穩產生亂碼，會直接拋出 `UnicodeDecodeError` 並觸發重連機制 (`_reconnect`)。這是不正確的——**雜訊不該導致連線重設**。
* **改進建議**：
  改用 `raw_data.decode('utf-8', errors='ignore')` 進行解碼，忽略亂碼字元，並交由 JSON 解析器過濾，僅記錄解析失敗日誌，而不觸發重連。

---

## 3. 可維護性與可擴充性審查 (Maintainability & Extensibility)

### 3.1 硬編碼 (Hardcoding) 嚴重，缺乏配置檔案
* 序列埠 `"COM3"` 與波特率 `115200` 硬編碼在 `main.py` 中。地圖初始點 `(23.5, 121.5)` 亦為硬編碼。
* **影響**：使用者若要變更序列埠，必須修改程式碼。
* **建議**：引進 `config.py`，從設定檔（如 `settings.json` 或 `.ini`）或環境變數讀取配置，或在 GUI 上提供下拉選單讓使用者選取可用序列埠。

### 3.2 違反依賴倒置原則 (Dependency Inversion Principle)
* `StorageObserver` 直接在 `__init__` 中實例化了 `CsvDataStorage()` 與 `JsonDataStorage()`。
* **影響**：如果以後要更換儲存庫（例如改用 SQLite 或是 InfluxDB 時），必須直接修改 `StorageObserver` 的內部邏輯。
* **建議**：應使用依賴注入 (Dependency Injection)，將 `DataStorage` 的實例在外部建立後傳入 `StorageObserver`。

### 3.3 代碼冗餘與排版混亂
* [visualization_tools.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/visualizers/visualization_tools.py) 中 `quaternion_multiply` 被定義了兩次（L17-27 與 L52-61）。
* `LineChartDrawer` 中使用 `np.roll` 來滾動 100,000 個元素的陣列。當資料頻率極高時，記憶體複製的負載較高，且 preallocate 的數組過大（100,000 點在畫面只能看 100 點的情況下不必要）。

---

## 4. 改進路線圖與修復方案 (Recommended Refactoring Plan)

為了解決以上問題，我們建議依以下順序進行優化：

### 第一階段：修復崩潰與效能漏洞 (Stability & Performance)
1. **重構日誌重定向**：利用 Qt 訊號傳遞日誌，確保主線程操作 QTextEdit。
2. **優化 JSON 儲存**：改為定期批次緩衝寫入，或是移除不必要的高頻 JSON 儲存，僅保留 CSV 追加寫入。
3. **重構地圖刷新**：引入 JavaScript 橋接，利用 `runJavaScript` 改寫 `LocationDisplayer`。
4. **健全重連機制**：使用 `threading.Event` 替換 `time.sleep`，並修正 `FileNotFoundError` 的無限死循環。

### 第二階段：提昇可維護性 (Extensibility)
1. **增加配置管理**：設計一個簡單的 `settings.json` 管理 COM Port、Baudrate、與地圖初始座標。
2. **清理冗餘代碼**：刪除重複定義的函數，優化數據圖表的 circular buffer 邏輯。

---
本報告由 Antigravity 整理編寫，旨在提昇系統在實際飛行任務中的可靠度。
