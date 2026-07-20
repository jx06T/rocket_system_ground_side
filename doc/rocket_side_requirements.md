# 火箭航電端 (Avionics Side) 遠端指令接收與觸發規範文件

本規範文件說明地面站 (Ground Station) 透過地面 LoRa 發射端下傳之緊急指令格式，以及火箭航電系統在接收與執行該指令時的硬體/軟體解鎖要求。

---

## 1. 下行指令 (Downlink Command) 特殊秘鑰字串

為防止賽場上其他隊伍無線電訊號干擾或隨機雜訊造成誤觸發，地面站不會下傳通用的 ASCII Key-Value 格式，而是採用帶有特定隊伍防偽秘鑰 (Secret Token String) 的字串。

### 指令對照表

| 地面站輸入指令 | 遠端控制動作 | 實際下傳之 LoRa 特殊字串 (包含 CRLF 換行) | 發送次數與頻率 | 火箭端解鎖與執行邏輯 |
| :--- | :--- | :--- | :--- | :--- |
| `/arm` | **系統遠端解鎖** (System ARM) | `#CMD:ARM_SYSTEM_SALT7763#\r\n` | 連續發送 4 次 (每 0.7s 一幀) | 刷新並啟動 30 秒倒數發火解鎖窗口 (`armExpiryTime = millis() + 30000`) |
| `/dpl` | **遠端強制開傘** (Parachute Deploy) | `#CMD:FORCE_DPL_SALT9981#\r\n` | 連續發送 4 次 (每 0.7s 一幀) | 僅於 **30 秒解鎖窗口內** 且滿足飛行狀態時，驅動開傘火工品 |
| `/abg` | **遠端開啟氣囊** (Airbag Deploy) | `#CMD:OPEN_ABG_SALT8872#\r\n` | 連續發送 4 次 (每 0.7s 一幀) | 僅於 **30 秒解鎖窗口內** 且滿足飛行狀態時，驅動氣囊電路 |

> ⚠️ **指令輸入規範**：所有地面站終端指令必須以 `/` 開頭（如 `/arm`, `/dpl`, `/abg`）。

---

## 2. 地面站發送機制說明

1. **半雙工錯開 (Burst Transmission)**：地面站在接獲指令後，會連續寫入 serial 4 次（每次間隔 **0.7 秒 / 700 毫秒**）。由於火箭端遙測發送頻率為 **2Hz (每 500ms 一幀)**，0.7 秒的間隔能確保 4 次嘗試中與火箭端的 TX 時間窗口錯開，順利被航電 LoRa 模組在 RX 狀態捕捉。
2. **無二次確認直接發射**：地面站介面已取消彈窗驗證，輸入按 Enter 即刻寫入 serial。

---

## 3. 火箭航電端 (Rocket Board) 軟體處理與安全防護要求

為保證地面站誤按或上電前發送指令時不會造成意外火工品發火，航電端軟體需實作以下防禦機制：

### 3.1 雙重人工/自動保險機制
1. **人工保險 (ARM Safety Window)**：
   * 火箭預設處於 **DISARMED (鎖定)** 狀態，即便收到 `/dpl` 或 `/abg` 指令亦不會驅動火工品。
   * 收到 `#CMD:ARM_SYSTEM_SALT7763#` 後，航電啟動或刷新 **30 秒解鎖倒數計時**。超過 30 秒未執行開傘或氣囊指令，系統自動回歸 DISARMED 狀態。
2. **時間/狀態硬體鎖 (Boottime & Stage Safety Interlock)**：
   * 當系統啟動時間 $T < 10,000\text{ ms}$ (發射前/IDLE 狀態) 時，航電端強制忽略所有觸發指令。
   * 強制開傘指令僅允許於 `STAGE >= LAUNCHED` (升空/下降階段) 時觸發。

### 3.2 串列埠接收與比對邏輯 (Arduino / C++ 範例)

```cpp
// 航電端接收範例程式碼 (以 Arduino Serial 為例)
String incomingString = "";
unsigned long armExpiryTime = 0; // ARM 解鎖到期時間戳 (ms)

void setup() {
    Serial1.begin(9600); // 對應 LoRa 模組
}

void loop() {
    unsigned long currentTimeMs = millis();
    bool isArmed = (currentTimeMs < armExpiryTime); // 檢查是否在 30s 解鎖窗口內

    if (Serial1.available() > 0) {
        incomingString = Serial1.readStringUntil('\n');
        incomingString.trim(); // 移除首尾空白與 \r

        // 1. 驗證遠端解鎖指令 (ARM)
        if (incomingString.equals("#CMD:ARM_SYSTEM_SALT7763#")) {
            armExpiryTime = currentTimeMs + 30000; // 開啟/刷新 30 秒解鎖窗口
            Serial1.println("MSG SUCCESS System ARMED for 30 seconds"); // 下傳確認訊息給地面站
        }
        // 2. 驗證強制開傘指令 (DPL)
        else if (incomingString.equals("#CMD:FORCE_DPL_SALT9981#")) {
            // 雙重保險：必須在起飛 10 秒後、處於飛行階段、且在 30 秒 ARM 窗口內
            if (isArmed && currentTimeMs >= 10000 && currentFlightStage >= STAGE_LAUNCHED) {
                triggerParachutePyrotechnic(); // 驅動開傘電路
                Serial1.println("MSG SUCCESS Parachute deployed successfully");
            } else {
                Serial1.println("MSG ERROR Parachute trigger rejected: System DISARMED or Invalid Stage");
            }
        }
        // 3. 驗證開啟氣囊指令 (ABG)
        else if (incomingString.equals("#CMD:OPEN_ABG_SALT8872#")) {
            if (isArmed && currentTimeMs >= 10000 && currentFlightStage >= STAGE_LAUNCHED) {
                triggerAirbagMosfet(); // 驅動充氣氣囊電路
                Serial1.println("MSG SUCCESS Airbag inflation started");
            }
        }
    }
}
```

---

## 4. 驗證與調試建議

1. **未 ARM 測試**：上電點火滿 10 秒後，未發送 `/arm` 直接發送 `/dpl`，確認航電忽略指令不發火。
2. **ARM 30 秒窗口測試**：先發送 `/arm`，於 30 秒內發送 `/dpl`，確認開傘 Pin 腳拉高高電位；若超過 30 秒才發送 `/dpl`，確認已自動過期不發火。
