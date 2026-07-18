
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QListWidget,QStyledItemDelegate
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
        self.list_widget.clear()
        self.list_widget.addItems([ "  "+i for i in self.stages])
        self.list_widget.setItemDelegate(CustomDelegate())
        
    def update(self, stage:int, failedTasks:List[int]):
        """stage 目前任務階段;failedTasks 失敗任務列表"""
        if stage < 0 or stage >= len(self.stages):
            return
            
        self.visited_stages.add(stage)
        self.current_stage = stage
        
        for i in range(len(self.stages)):
            item = self.list_widget.item(i)
            if not item:
                continue
                
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