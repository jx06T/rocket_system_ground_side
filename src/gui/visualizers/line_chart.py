import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout

class LineChartDrawer:
    def __init__(self, container_widget, num_lines=1, window_width=100,y_range = (-180,180)):
        self.window_width = window_width
        self.y_range = y_range
        self.max_len = 100000
        self.num_lines = num_lines  # 支持多條線

        if container_widget.layout() is None:
            container_widget.setLayout(QVBoxLayout())

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setYRange(*self.y_range)

        # 初始化數據 (num_lines 條線，每條 max_len 點)
        self.data_points = np.zeros((num_lines, self.max_len))
        self.time_axis = np.zeros(self.max_len)
        self.current_x = 0 

        # 創建多條曲線
        colors = ['g', 'r', 'b', 'm', 'c', 'y']  # 預設顏色
        self.curves = [
            self.plot_widget.plot(self.time_axis, self.data_points[i], pen=pg.mkPen(color=colors[i % len(colors)], width=2))
            for i in range(num_lines)
        ]

        container_widget.layout().addWidget(self.plot_widget)

    def update_chart(self, data_values, auto=False):
        """data_values 應該是一個 list 或 np.array，包含每條線的數據"""
        self.current_x += 1 

        if len(self.time_axis) < self.max_len:
            self.time_axis = np.append(self.time_axis, self.current_x)
        else:
            self.time_axis = np.roll(self.time_axis, -1)
            self.time_axis[-1] = self.current_x

        for i in range(self.num_lines):
            value = data_values[i] if i < len(data_values) else 0  # 確保數據不會超出範圍
            if len(self.data_points[i]) < self.max_len:
                self.data_points[i] = np.append(self.data_points[i], value)
            else:
                self.data_points[i] = np.roll(self.data_points[i], -1)
                self.data_points[i][-1] = value

            self.curves[i].setData(self.time_axis, self.data_points[i])

        if auto:
            self.plot_widget.setXRange(self.current_x - self.window_width, self.current_x)
