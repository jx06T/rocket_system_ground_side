from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QListWidget, QStyledItemDelegate, QAbstractItemView
from PyQt6.QtCore import Qt
from datetime import datetime
from typing import List


class CustomDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(30) 
        self.padding = 10
        return size

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
        
    def update(self, stage:int, failedTasks:List[int], timestamp: datetime = None):
        """stage 目前任務階段;failedTasks 失敗任務列表;timestamp 當前遙測時間戳"""
        if stage < 0 or stage >= len(self.stages):
            return
            
        self.visited_stages.add(stage)
        self.current_stage = stage
        
        # 當第一次達到某個階段，記錄時間戳
        if timestamp is None:
            timestamp = datetime.now()
        if stage not in self.stage_times:
            self.stage_times[stage] = timestamp
            
        # 容錯處理：如果已經進入 LAUNCH (2) 或之後的階段，但還沒有 T0 (LAUNCH 的時間)，則將當前時間作為 T0
        if stage >= 2 and 2 not in self.stage_times:
            self.stage_times[2] = timestamp
        
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