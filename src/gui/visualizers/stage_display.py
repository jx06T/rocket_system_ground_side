from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QListWidget, QStyledItemDelegate, QAbstractItemView, QStyle
from PyQt6.QtCore import Qt
from datetime import datetime


class CustomDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(30) 
        self.padding = 10
        return size

    def paint(self, painter, option, index):
        # 💡 移除滑鼠懸停 (hover)、選取與焦點狀態，防止不可互動元件顯示高亮白底干擾閱讀
        option.state &= ~QStyle.StateFlag.State_MouseOver
        option.state &= ~QStyle.StateFlag.State_Selected
        option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)

EVENT_STAGES = {
    2: ("IGNITION", "#00E676"),
    4: ("BURNOUT", "#FF9100"),
    6: ("APOGEE", "#FFD600"),
    7: ("PARACHUTE_DEPLOY", "#D500F9"),
    9: ("TOUCHDOWN", "#00E5FF"),
    10: ("AIRBAG_DEPLOY", "#1DE9B6"),
}

class StageDisplayer:
    def __init__(self, list_widget:QListWidget):
        self.list_widget:QListWidget = list_widget 
        self.current_stage = -1
        self.visited_stages = set()
        self.marked_events = set()
        self.stages = [
            "IDLE",
            "ARMED",
            "IGNITION",
            "POWERED_FLIGHT",
            "BURNOUT",
            "COASTING",
            "APOGEE",
            "PARACHUTE_DEPLOY",
            "DESCENT",
            "TOUCHDOWN",
            "AIRBAG_DEPLOY",
            "LANDED"
        ]
        self.stage_times = {} # 紀錄各個階段初次達到的時間戳
        
        # 暫時移除滑鼠點擊/選中高亮變白功能：禁用選取與焦點
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setStyleSheet("""
            QListWidget::item:hover {
                background-color: transparent;
            }
        """)

        self.list_widget.clear()
        self.list_widget.addItems([ "  "+i for i in self.stages])
        self.list_widget.setItemDelegate(CustomDelegate())
        
    def update(self, stage:int, timestamp: datetime = None):
        """stage 目前任務階段;timestamp 當前遙測時間戳
        
        若傳入的是首次發生的瞬態事件 (Event)，將傳回 (True, event_name, color)。
        其餘狀態或重複幀則傳回 (False, None, None)。
        """
        is_new_event = False
        event_name = None
        event_color = None

        if stage in EVENT_STAGES and stage not in self.marked_events:
            self.marked_events.add(stage)
            is_new_event = True
            event_name, event_color = EVENT_STAGES[stage]

        if stage < 0 or stage >= len(self.stages):
            return is_new_event, event_name, event_color

            
        # 當第一次達到某個階段，記錄時間戳 (去重處理：後續連發的重複幀不覆蓋時間)
        if timestamp is None:
            timestamp = datetime.now()
        if stage not in self.stage_times:
            self.stage_times[stage] = timestamp
            
        # 容錯處理：如果已經進入 IGNITION (2) 或之後的階段，但還沒有 T0 (IGNITION 的時間)，則將當前時間作為 T0
        if stage >= 2 and 2 not in self.stage_times:
            self.stage_times[2] = timestamp

        import logging
        logger = logging.getLogger("src.gui.stage_display")
        
        # 檢測階段轉換日誌 (僅在階段變更時發送一次)
        if stage != self.current_stage:
            old_stage_name = self.stages[self.current_stage] if self.current_stage >= 0 else "NONE"
            new_stage_name = self.stages[stage]
            
            # 建立時間後綴
            time_suffix = ""
            if stage == 2:  # IGNITION (T0)
                time_suffix = " (T0)"
            elif stage > 2:
                if stage in self.stage_times and 2 in self.stage_times:
                    dt = (self.stage_times[stage] - self.stage_times[2]).total_seconds()
                    time_suffix = f" (T+{dt:.2f}s)"
            
            logger.info(f"[STAGE TRANSITION] Rocket stage/event changed: {old_stage_name} -> {new_stage_name}{time_suffix}")
            
            # 偵測被跳過的階段 (索引在 current_stage+1 ~ stage-1 之間且從未造訪)
            start_check = max(0, self.current_stage + 1) if self.current_stage >= 0 else 0
            for skipped_idx in range(start_check, stage):
                if skipped_idx not in self.visited_stages:
                    logger.warning(f"[STAGE SKIPPED] Stage/Event '{self.stages[skipped_idx]}' was skipped (never received from telemetry)")

        self.visited_stages.add(stage)
        self.current_stage = stage

        # Health item updates removed; handled by dedicated UI component
        
        for i in range(len(self.stages)):
            item = self.list_widget.item(i)
            if not item:
                continue
                
            # 決定顯示的文字（含相對時間戳功能）
            stage_name = self.stages[i]
            display_text = f"  {stage_name}"
            
            if i == 2:  # IGNITION (T0)
                if 2 in self.stage_times:
                    display_text = f"  {stage_name} (T0)"
            elif i > 2:  # POWERED_FLIGHT ~ LANDED
                if i in self.stage_times and 2 in self.stage_times:
                    dt = (self.stage_times[i] - self.stage_times[2]).total_seconds()
                    display_text = f"  {stage_name} (T+{dt:.2f}s)"
                    
            item.setText(display_text)
                
            if i < stage:
                item.setForeground(QBrush(QColor(0, 0, 0)))
                # 如果歷史狀態中，有些狀態在 visited_stages 中沒有紀錄到，說明被「跳過」了
                if i not in self.visited_stages:
                    item.setBackground(QBrush(QColor(180, 70, 70)))
                else:
                    item.setBackground(QBrush(QColor(150, 200, 150)))

            elif i == stage:
                item.setForeground(QBrush(QColor(0, 0, 0)))
                item.setBackground(QBrush(QColor(200, 200, 200)))

            else:
                item.setBackground(QBrush(QColor(254, 254, 254)))
                item.setForeground(QBrush(QColor(140, 140, 140)))

        return is_new_event, event_name, event_color