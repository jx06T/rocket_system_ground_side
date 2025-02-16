# rocket_system_ground_side
###### *version-V1.0.0* 
---
## 簡介
- 火箭系統的地面端程式
- 使用 PyQt 製作 GUI
- 從序列埠讀取資料並即時繪製圖表與進行簡單分析
 
## 序列埠資料格式
```
<type:"telemetry"|"command"|"error">:<data:json>
```
### 規範
- `<type>` 指資料的**用途**，其所需要資料參見下表定義。
- `<data>` 是 JSON 格式的有效數據，Key 請遵循 camelCase 規則命名。
- 資料**請勿**換行。

#### 支持的 Type 列表
| Type         | 說明                        | data 格式 |
|-------------|---------------------------|---------------|
| `telemetry` | 傳輸感測器數據 | `{location:[float,float],failedTasks:str[],"stage":int,"rotationRoll":float,"rotationPitch":float,"direction":float}` *TBD|
| `command`   | 控制指令                  | `{"action":str}` |
| `error`   | 錯誤訊息               | `{"message":str}` |

### 範例
``` 
telemetry:{"stage":0,"rotationRoll":0,"rotationPitch":0,"direction":90}
```

## 溝通與運行邏輯
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

## 更新
### 1.0
```
1.0.2

1.0.1

1.0.0

```

## 待辦
- 
