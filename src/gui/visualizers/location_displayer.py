import folium
import logging
from typing import Tuple

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl ,QTimer

class LocationDisplayer:
    def __init__(self, widget: QWidget, initial_location: Tuple[float, float] = (23.5, 121.5)):
        """
        初始化LocationDisplayer
        
        Args:
            widget (QWidget): 用於顯示地圖的Qt widget
            initial_location (Tuple[float, float]): 初始位置的(緯度, 經度)，默認為台灣中心位置
        """
        self.widget = widget
        self.layout = QVBoxLayout(widget)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0) 

        self.web_view = QWebEngineView()
        self.layout.addWidget(self.web_view)
        
        self.logger = logging.getLogger(__name__)

        # 初始化地圖
        self.current_location = initial_location
        self.map_obj = None
        self.temp_file = None
        self.create_map(initial_location)


    def create_map(self, location: Tuple[float, float]):
        """創建新的地圖"""
        # 創建地圖對象，縮放級別設為12
        self.map_obj = folium.Map(
            location=location,
            zoom_start=12,
            tiles='OpenStreetMap'
        )
        
        # 添加位置標記
        folium.Marker(
            location,
            popup='Current Location',
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(self.map_obj)
        
        # 在WebView中顯示地圖
        html_string = self.map_obj.get_root().render()
        self.web_view.setHtml(html_string)
        # self.web_view.setUrl(QUrl.fromLocalFile(self.temp_file))
        
    def update(self, location: Tuple[float, float]):
        """
        更新位置標記
        
        Args:
            location (Tuple[float, float]): 新的(緯度, 經度)位置
        """

        if location != self.current_location:
            self.current_location = location
            self.create_map(location)
    