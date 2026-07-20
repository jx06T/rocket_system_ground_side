import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout
from typing import List, Dict, Any


class LineChartDrawer:
    """
    多線折線圖繪製器。
    支援多條曲線的個別顯示/隱藏控制、自動 Y 軸縮放與圖例顯示。
    """
    def __init__(self, container_widget, window_width: int = 100,
                 curve_configs: List[Dict[str, Any]] = None):
        """
        Args:
            container_widget: 用於嵌入圖表的 QWidget 容器。
            window_width: X 軸自動捲動時顯示的資料點寬度。
            curve_configs: 每條曲線的配置列表，每個 dict 包含：
                - 'label' (str): 圖例名稱
                - 'color' (str or tuple): 線條顏色
                - 'width' (float): 線條粗細
        """
        if curve_configs is None:
            curve_configs = [{'label': 'data', 'color': 'g', 'width': 2}]

        self.window_width = window_width
        self.max_len = 100000
        self.num_lines = len(curve_configs)

        if container_widget.layout() is None:
            container_widget.setLayout(QVBoxLayout())

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        # 啟用 Y 軸自動縮放，取代固定範圍以適應不同量級的火箭數據
        self.plot_widget.enableAutoRange('y', True)

        # 加入圖例以標示各條曲線名稱
        self.plot_widget.addLegend(offset=(5, 5))

        # 修復 Bug：改用空陣列初始化，避免圖表左側出現長段零值尾巴
        self.data_points: List[np.ndarray] = [np.array([]) for _ in range(self.num_lines)]
        self.time_axis: np.ndarray = np.array([])
        self.current_x: int = 0

        # 根據 curve_configs 創建各條曲線
        self.curves: List[pg.PlotDataItem] = []
        for cfg in curve_configs:
            pen = pg.mkPen(
                color=cfg.get('color', 'g'),
                width=cfg.get('width', 2)
            )
            curve = self.plot_widget.plot(
                pen=pen,
                name=cfg.get('label', 'data')
            )
            self.curves.append(curve)

        container_widget.layout().addWidget(self.plot_widget)

    def set_curve_visible(self, index: int, visible: bool) -> None:
        """設定指定曲線的顯示狀態。供外部勾選框的 stateChanged 信號呼叫。"""
        if 0 <= index < len(self.curves):
            self.curves[index].setVisible(visible)

    def update(self, data_values: List[float], auto_scroll: bool = False, x_value: float = None) -> None:
        """
        推送新的資料點並更新所有曲線。
        Args:
            data_values: 每條曲線最新的數值，順序對應 curve_configs。
            auto_scroll: 是否自動捲動 X 軸以追蹤最新資料。
            x_value: 選填。X 軸數值（例如地面站接收時間戳）。若未提供則自動累加。
        """
        if x_value is not None:
            curr_x = x_value
        else:
            self.current_x += 1
            curr_x = self.current_x

        # 更新時間軸：未滿 max_len 前 append，之後改用 roll 滾動覆蓋
        if len(self.time_axis) < self.max_len:
            self.time_axis = np.append(self.time_axis, curr_x)
        else:
            self.time_axis = np.roll(self.time_axis, -1)
            self.time_axis[-1] = curr_x

        for i in range(self.num_lines):
            value = float(data_values[i]) if i < len(data_values) else 0.0

            if len(self.data_points[i]) < self.max_len:
                self.data_points[i] = np.append(self.data_points[i], value)
            else:
                self.data_points[i] = np.roll(self.data_points[i], -1)
                self.data_points[i][-1] = value

            # 無論曲線是否可見，皆更新數據以確保重新顯示時數據為最新狀態
            self.curves[i].setData(self.time_axis, self.data_points[i])

        if auto_scroll:
            self.plot_widget.setXRange(curr_x - self.window_width, curr_x)

    def set_x_link(self, master_drawer: 'LineChartDrawer' = None) -> None:
        """綁定或解綁 X 軸縮放與平移檢視。傳入 master_drawer 進行同步，傳入 None 則獨立。"""
        target_widget = master_drawer.plot_widget if master_drawer else None
        self.plot_widget.setXLink(target_widget)

    def add_event_marker(self, x_value: float, label_text: str, color: str = '#D500F9') -> None:
        """
        在圖表指定 X 軸時間點劃出一條垂直事件虛線，並附帶文字標籤。
        """
        pen = pg.mkPen(color=color, width=1.5, style=pg.QtCore.Qt.PenStyle.DashLine)
        vline = pg.InfiniteLine(pos=x_value, angle=90, pen=pen, movable=False)
        self.plot_widget.addItem(vline)

        # 文字標記懸浮在虛線頂端附近
        text_item = pg.TextItem(text=label_text, color=color, anchor=(0, 0))
        text_item.setPos(x_value, 0)
        # 動態將文字放在 Y 軸目前的頂部區域
        vb = self.plot_widget.getViewBox()
        if vb:
            y_range = vb.viewRange()[1]
            text_item.setPos(x_value, y_range[1] * 0.9)
        self.plot_widget.addItem(text_item)

