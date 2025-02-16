
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
        self.current_stage = 0
        self.stages = [
            "Pre-launch Preparation",
            "Ignition & Liftoff",
            "Ascent - 25% Altitude",
            "Ascent - 50% Altitude",
            "Ascent - 75% Altitude",
            "Apogee ",
            "Parachute Deployment",
            "Descent Altitude",
            "Landing"
        ]
        self.list_widget.addItems([ "  "+i for i in self.stages])
        self.list_widget.setItemDelegate(CustomDelegate())
        
    def update(self, stage:int,failedTasks:List[int]):
        """stage 目前任務階段;failedTasks 失敗任務列表"""
        if stage == self.current_stage:
            return
        
        for i in range(len(self.stages)):
            item = self.list_widget.item(i)
            if i < stage:
                item.setForeground(QBrush(QColor(0, 0, 0)))
                if i in  failedTasks:
                    item.setBackground(QBrush(QColor(180, 70, 70)))
                else :
                    item.setBackground(QBrush(QColor(150, 200, 150)))

            elif i == stage:
                item.setForeground(QBrush(QColor(0, 0, 0)))
                item.setBackground(QBrush(QColor(200, 200, 200)))

            else:
                item.setBackground(QBrush(QColor(254, 254, 254)))
                item.setForeground(QBrush(QColor(140, 140, 140)))