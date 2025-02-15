import numpy as np
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPen, QColor

# 繪製圖表的類
class LineChartDrawer:
    def __init__(self, graphics_view: QGraphicsView):
        self.view = graphics_view
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.data_points = np.zeros((20, 2))  # 儲存 20 個點 (x, y)
        self.x_offset = 0  # 用來控制折線圖向左移動的偏移量

        # 繪製坐標軸
        self.draw_axes()

    def update_chart(self, data_value: float):
        # 每次新增新點時，將現有的點往左移動
        self.x_offset += 5  # 每個點的寬度設置為 10px

        # 使用 np.roll 來將數據點往左移動
        self.data_points = np.roll(self.data_points, shift=-1, axis=0)
        self.data_points[-1] = [self.x_offset, data_value]  # 更新最後一個點

        # 刪除最舊的數據點
        if len(self.scene.items()) > 20:  # 當顯示的點超過 20 個時，移除最舊的點
            self.scene.removeItem(self.scene.items()[0])

        # 繪製新的折線
        for i in range(1, len(self.data_points)):
            prev_point = self.data_points[i - 1]
            curr_point = self.data_points[i]
            line = QGraphicsLineItem(prev_point[0], prev_point[1], curr_point[0], curr_point[1])
            line.setPen(QPen(QColor(0, 255, 0)))  # 設置顏色為綠色
            self.scene.addItem(line)

        # 添加新的點
        new_point = QPointF(self.data_points[-1][0], self.data_points[-1][1])
        self.scene.addEllipse(new_point.x() - 2, new_point.y() - 2, 4, 4, pen=QPen(QColor(255, 0, 0)), brush=QColor(255, 0, 0))  # 小紅點

        # 使視圖滾動到右側以顯示新的點
        self.view.ensureVisible(new_point.x() - 50, new_point.y() - 50, 100, 100)

    def draw_axes(self):
        # 畫 Y 軸
        y_axis = QGraphicsLineItem(0, 0, 0, 300)
        y_axis.setPen(QPen(QColor(0, 0, 0)))  # 黑色
        self.scene.addItem(y_axis)

        # 畫 Y 軸數字
        for i in range(-180, 181, 10):
            text = QGraphicsTextItem(str(i))
            text.setPos(-20, i)
            self.scene.addItem(text)
