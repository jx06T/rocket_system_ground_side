# rocket_system_ground_side
###### *version-V1.0.5* 
---
## 簡介
- 火箭系統的地面端程式
- 使用 PyQt 製作 GUI
- 從序列埠讀取資料並即時繪製圖表與進行簡單分析
- 透過 OpenGL 即時繪製火箭姿態
- 即時繪制數據折線圖
- 顯示火箭任務階段
- 透過 Folium 繪製火箭經緯度座標 *TBD
- 可能有一半的程式碼是 ai 寫的（？
 
## 序列埠資料格式
```
<type:"telemetry"|"command"|"error">:<data:json>
```
### 規範
- `<type>` 指資料的**用途**，其所需要資料參見下表定義。
- `<data>` 是 **JSON 格式**的有效數據，Key 請遵循 camelCase 規則命名。
- 資料**請勿**換行。

#### 支持的 Type 列表
| Type         | 說明                        | data 格式 |
|-------------|---------------------------|---------------|
| `telemetry` | 傳輸感測器數據 | `{location:[float,float],failedTasks:str[],"stage":int,"rotationRoll":float,"rotationPitch":float,"direction":float}` *TBD|
| `command`   | 控制指令                  | `{"action":str}` |
| `error`   | 錯誤訊息               | `{"message":str}` |

### 範例
``` 
telemetry:{"location":[-21,-145],"failedTasks":[],"stage":0,"rotationRoll":0,"rotationPitch":0,"direction":90}
```

> [!CAUTION]
> 資料格式與內容在初步開發時依照 **microbit** 所取得格式設計，實際應用仍待整合後修改
>
> 目前資料格式僅有 **telemetry** 這一項，故傳送資料時僅需傳送 json 格式的資料就好，不要附加任何額外字符
>

## 執行
1. 安裝 `requirements.txt` 中的依賴
2. 若有 **microbit** 可透過其執行 `microbit-test.hex` 並透過 USB 連接電腦
3. 配置 `main.py` 中的 `communicator = SerialCommunicator("COM3", 115200)` 所需之序列埠編號
4. 運行 `main.py`

> [!NOTE]  
> 目前並未檢查 `requirements.txt` 之依賴是否完整
> 
> 若無 **microbit** 開發設備需依照上方所列之需求實現地面端接收晶片，並使其與電腦連接
>

## 截圖
![1](/doc/1.png)
![2](/doc/2.png)
![3](/doc/3.png)


## 運行邏輯
### 各端職責
``` mermaid
classDiagram
    class 火箭控制晶片 {
        執行階段
        失敗列表
        感測器數據
        控制火箭行為()
        回傳感測器數據()
        儲存感測器數據()
    }

    class 地面端接收晶片 {
        波特率:115200 *TBD
        接收火箭回傳數據()
        轉譯並傳送給電腦()
    }

    class 電腦端 {
        波特率:115200 *TBD
        電腦端數據:csv *TBD
        初始數據
        即時顯示數據()
        簡單分析數據()
        電腦端儲存數據()
    }
```
### 流程
``` mermaid
sequenceDiagram
    autonumber
    participant R as 火箭控制晶片
    participant G as 地面端接收晶片
    participant C as 電腦端

    Note right of R:透過 LoRa 遠程通訊 
    Note right of G:透過 USB 序列埠通訊 

    R ->> G: 感測器資料
    G ->> C: 感測器資料
    Note over C : 使用者透過重力感測器校準初始姿態
    Note over R : 發射


    loop 每100毫秒 *TBD 直到使用者停止
        R ->> G: 感測器資料
        G ->> C: 感測器資料
        Note over C : 數據可視化

        break 火箭發生未預期錯誤
            R-->>G: 錯誤訊息
            G-->>C: 錯誤訊息
            Note over C : 顯示錯誤資訊
        end
        break 地面端未收到資料
            G-->>C: 錯誤訊息
            Note over C : 顯示錯誤資訊
        end
    end

```

> [!NOTE]  
> 錯誤回報功能尚未實作
>
> 使用者停止功能向未實現
>

## 更新
### 1.0
```

1.0.5
地圖顯示實現
姿態顯示 Bug 修復
解決地圖與姿態顯示之衝突

1.0.4
姿態顯示實現
折線圖更新
Bug 修復

1.0.3
折線圖繪製多條線實現
狀態列表完成
log 區塊整合
底部狀態欄完成
GUI 更新 

1.0.2
折線圖繪製實現
狀態列表實現

1.0.1
序列埠通訊方法完成
觀察者模式實現
本地儲存模塊完成

1.0.0
初步架構完成
初步 GUI 布局完成

```

## 待辦
- 折線圖分析
- 折線圖 x 軸用實際時間
- 改由角速度推算目前姿態
- 初始狀態透過重力感測器校準姿態
- 飛行過程極值紀錄
- 飛行過程事件時間紀錄
- 重力資料作圖
- 地圖功能最佳實現?
- 本地儲存格式？
- 錯誤回報功能尚未實作
- 使用者停止功能向未實現
- 讀取序列埠發生未捕獲錯誤導致視窗退出問題修復
