import logging
from typing import Tuple

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView

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

        self.current_location = initial_location
        self.map_initialized = False
        self.create_map(initial_location)

    def create_map(self, location: Tuple[float, float]):
        """創建新的地圖並載入"""
        lat, lng = location
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                html, body, #map {{ width: 100%; height: 100%; margin: 0; padding: 0; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                // 初始中心點設在台灣 (縮放等級為 7，顯示全島概覽，無標記與軌跡)
                var map = L.map('map').setView([{lat}, {lng}], 7);
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; OpenStreetMap'
                }}).addTo(map);

                var marker = null;
                var polyline = null;
                var pathCoords = [];

                function updateMarker(lat, lng) {{
                    var newLatLng = new L.LatLng(lat, lng);
                    pathCoords.push([lat, lng]);

                    if (marker === null) {{
                        // 首次收到定位：建立標記與軌跡線，並縮放到詳細層級 15
                        marker = L.marker(newLatLng).addTo(map)
                            .bindPopup('Current Location')
                            .openPopup();
                        polyline = L.polyline(pathCoords, {{
                            color: '#FF3B30',
                            weight: 4,
                            opacity: 0.85
                        }}).addTo(map);
                        map.setView(newLatLng, 15);
                    }} else {{
                        // 後續定位更新
                        marker.setLatLng(newLatLng);
                        polyline.setLatLngs(pathCoords);
                        map.panTo(newLatLng);
                    }}
                }}
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
        self.map_initialized = True
        self.current_location = location
        
    def update(self, location: Tuple[float, float]):
        """
        更新位置標記
        
        Args:
            location (Tuple[float, float]): 新的(緯度, 經度)位置
        """
        if location != self.current_location:
            self.current_location = location
            if self.map_initialized:
                lat, lng = location
                js_code = f"if (typeof updateMarker === 'function') {{ updateMarker({lat}, {lng}); }}"
                self.web_view.page().runJavaScript(js_code)
            else:
                self.create_map(location)

    