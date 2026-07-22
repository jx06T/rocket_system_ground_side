import logging
import time
from typing import Tuple, Any

class LoraCommand:
    """LoRa 遠端控制指令金鑰定義"""
    ARM = ("arm", b"#CMD:ARM_SYSTEM_SALT7763#\r\n", "系統遠端解鎖 (ARM)")
    DPL = ("dpl", b"#CMD:FORCE_DPL_SALT9981#\r\n", "遠端強制開傘 (DPL)")
    ABG = ("abg", b"#CMD:OPEN_ABG_SALT8872#\r\n", "開啟氣囊 (ABG)")

    @classmethod
    def get_token(cls, action: str) -> Tuple[bytes, str]:
        """依據 action 取得對應防偽秘鑰 Token 與人類可讀標籤"""
        action_lower = action.lower()
        if action_lower == "arm":
            return cls.ARM[1], cls.ARM[2]
        elif action_lower == "dpl":
            return cls.DPL[1], cls.DPL[2]
        elif action_lower == "abg":
            return cls.ABG[1], cls.ABG[2]
        else:
            token = f"#CMD:{action}#\r\n".encode('utf-8')
            label = f"自訂遠端指令 ({action})"
            return token, label


class LoraProtocolHandler:
    """LoRa 通訊協定處理器（支援獨立頻道 ch1/ch2 實例化）"""
    def __init__(self, channel_id: str = "ch1"):
        self.channel_id = channel_id
        self.logger = logging.getLogger(f"LoraProtocol_{channel_id.upper()}")

    def send_command(
        self,
        communicator: Any,
        action: str,
        repeat_count: int = 4,
        burst_interval: float = 0.7
    ) -> Tuple[bool, int, str]:
        """
        透過傳輸介面 (Communicator) 重複連發下傳遠端控制指令
        :param communicator: 具備 send_bytes 方法的傳輸物件 (例如 SerialCommunicator)
        :param action: 指令代碼 (如 arm, dpl, abg)
        :param repeat_count: Burst 發送次數 (預設 4 次)
        :param burst_interval: 發送間隔時間以秒為單位 (預設 0.7s / 700ms，避開火箭 2Hz 時間窗口)
        :return: (是否成功傳送至少 1 幀, 成功傳送之幀數, 結果說明訊息)
        """
        raw_token, cmd_label = LoraCommand.get_token(action)
        self.logger.info(
            f"🟦 [CMD] Transmitting /{action} ({cmd_label}) over LoRa ({repeat_count}x bursts, {int(burst_interval * 1000)}ms interval)..."
        )

        sent_success = 0
        for _ in range(repeat_count):
            if communicator and hasattr(communicator, 'send_bytes'):
                if communicator.send_bytes(raw_token):
                    sent_success += 1
            time.sleep(burst_interval)

        if sent_success > 0:
            msg = f"🟦 [CMD] Successfully transmitted /{action} ({cmd_label}) over {self.channel_id.upper()} ({sent_success}/{repeat_count} bursts)."
            self.logger.info(msg)
            return True, sent_success, msg
        else:
            msg = f"🟥 [CMD] Transmit failed for /{action} ({cmd_label}): Serial port offline."
            self.logger.error(msg)
            return False, 0, msg
