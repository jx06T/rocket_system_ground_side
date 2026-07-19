from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QListWidget, QStyledItemDelegate, QAbstractItemView, QStyle
from PyQt6.QtCore import Qt
from datetime import datetime
from typing import List


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

class StageDisplayer:
    def __init__(self, list_widget:QListWidget):
        self.list_widget:QListWidget = list_widget 
        self.current_stage = -1
        self.visited_stages = set()
        self.stages = [
            "IDLE",
            "ARMED",
            "LAUNCH",
            "BOOST",
            "APOGEE",
            "DESCENT",
            "LANDED"
        ]
        self.stage_times = {} # 紀錄各個階段初次達到的時間戳
        self.logged_failed_tasks = set()
        self.module_names = {
            0: "BMP (Barometer)",
            1: "IMU (Inertial)",
            2: "LoRa (Telemetry Link)",
            3: "SD (SD Card Logger)"
        }

        
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
        # 增加健康狀態分割線與模組項目
        self.list_widget.addItem("  ------------------------")
        self.list_widget.addItem("  [ 箭端模組健康狀態 ]")
        for task_id in range(4):
            module_name = self.module_names[task_id]
            self.list_widget.addItem(f"  {module_name}: 正常")
        self.list_widget.setItemDelegate(CustomDelegate())
        
    def update(self, stage:int, failedTasks:List[int], timestamp: datetime = None):
        """stage 目前任務階段;failedTasks 失敗任務列表;timestamp 當前遙測時間戳"""
        if stage < 0 or stage >= len(self.stages):
            return
            
        # 當第一次達到某個階段，記錄時間戳
        if timestamp is None:
            timestamp = datetime.now()
        if stage not in self.stage_times:
            self.stage_times[stage] = timestamp
            
        # 容錯處理：如果已經進入 LAUNCH (2) 或之後的階段，但還沒有 T0 (LAUNCH 的時間)，則將當前時間作為 T0
        if stage >= 2 and 2 not in self.stage_times:
            self.stage_times[2] = timestamp

        # 檢測階段轉換日誌
        if stage != self.current_stage:
            old_stage_name = self.stages[self.current_stage] if self.current_stage >= 0 else "NONE"
            new_stage_name = self.stages[stage]
            
            # 建立時間後綴
            time_suffix = ""
            if stage == 2:  # LAUNCH
                time_suffix = " (T0)"
            elif stage > 2:
                if stage in self.stage_times and 2 in self.stage_times:
                    dt = (self.stage_times[stage] - self.stage_times[2]).total_seconds()
                    time_suffix = f" (T+{dt:.2f}s)"
            
            import logging
            logger = logging.getLogger("src.gui.stage_display")
            logger.info(f"[STAGE TRANSITION] Rocket stage changed: {old_stage_name} -> {new_stage_name}{time_suffix}")

        self.visited_stages.add(stage)
        self.current_stage = stage

        # 檢測模組健康狀態更新
        import logging
        logger = logging.getLogger("src.gui.stage_display")
        for task_id in range(4):
            is_failed = task_id in failedTasks
            was_failed = task_id in self.logged_failed_tasks
            module_name = self.module_names.get(task_id, f"Module {task_id}")
            if is_failed and not was_failed:
                self.logged_failed_tasks.add(task_id)
                logger.error(f"[MODULE FAULT] Sensor/Module error detected: {module_name} is abnormal (Failed/Offline)!")
            elif not is_failed and was_failed:
                self.logged_failed_tasks.remove(task_id)
                logger.info(f"[MODULE RECOVERY] Sensor/Module status restored: {module_name} is back to normal.")

        
        for i in range(len(self.stages)):
            item = self.list_widget.item(i)
            if not item:
                continue
                
            # 決定顯示的文字（含相對時間戳功能）
            stage_name = self.stages[i]
            display_text = f"  {stage_name}"
            
            if i == 2:  # LAUNCH
                if 2 in self.stage_times:
                    display_text = f"  {stage_name} (T0)"
            elif i > 2:  # BOOST, APOGEE, DESCENT, LANDED
                if i in self.stage_times and 2 in self.stage_times:
                    dt = (self.stage_times[i] - self.stage_times[2]).total_seconds()
                    display_text = f"  {stage_name} (T+{dt:.2f}s)"
                    
            item.setText(display_text)
                
            if i < stage:
                item.setForeground(QBrush(QColor(0, 0, 0)))
                # 如果歷史狀態中，有些狀態在 visited_stages 中沒有紀錄到，說明被「跳過」了
                # 或者在 failedTasks 中，標記為紅色背景
                if i not in self.visited_stages or i in failedTasks:
                    item.setBackground(QBrush(QColor(180, 70, 70)))
                else:
                    item.setBackground(QBrush(QColor(150, 200, 150)))

            elif i == stage:
                item.setForeground(QBrush(QColor(0, 0, 0)))
                if i in failedTasks:
                    item.setBackground(QBrush(QColor(180, 70, 70)))
                else:
                    item.setBackground(QBrush(QColor(200, 200, 200)))

            else:
                item.setBackground(QBrush(QColor(254, 254, 254)))
                item.setForeground(QBrush(QColor(140, 140, 140)))

        # 更新健康狀態分割線與項目的樣式
        sep_item = self.list_widget.item(len(self.stages))
        if sep_item:
            sep_item.setBackground(QBrush(QColor(254, 254, 254)))
            sep_item.setForeground(QBrush(QColor(180, 180, 180)))
            
        header_item = self.list_widget.item(len(self.stages) + 1)
        if header_item:
            header_item.setBackground(QBrush(QColor(245, 245, 245)))
            header_item.setForeground(QBrush(QColor(50, 50, 50)))

        for task_id in range(4):
            item_idx = len(self.stages) + 2 + task_id
            item = self.list_widget.item(item_idx)
            if item:
                module_name = self.module_names.get(task_id, f"Module {task_id}")
                is_failed = task_id in failedTasks
                if is_failed:
                    item.setText(f"  {module_name}: 異常 (FAULT)")
                    item.setForeground(QBrush(QColor(0, 0, 0)))
                    item.setBackground(QBrush(QColor(230, 100, 100))) # 紅色代表故障
                else:
                    item.setText(f"  {module_name}: 正常 (OK)")
                    item.setForeground(QBrush(QColor(0, 0, 0)))
                    item.setBackground(QBrush(QColor(150, 220, 150))) # 綠色代表正常