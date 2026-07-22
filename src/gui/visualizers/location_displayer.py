import logging
from typing import Tuple

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

class NonNavigablePage(QWebEnginePage):
    """自訂 QWebEnginePage，防止使用者因誤點地圖超連結（如版權資訊）跳轉至外部網頁"""
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if navigation_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

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
        self.web_view.setPage(NonNavigablePage(self.web_view))
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
                /* 停用版權與標示區域的點擊事件，防止誤觸跳轉 */
                .leaflet-control-attribution, .leaflet-control-attribution a {{
                    pointer-events: none !important;
                    cursor: default !important;
                    text-decoration: none !important;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                // 初始中心點設在台灣 (縮放等級為 7，顯示全島概覽，無標記與軌跡)
                var map = L.map('map', {{ attributionControl: true }}).setView([{lat}, {lng}], 7);
                if (map.attributionControl) {{
                    map.attributionControl.setPrefix(false); // 移除預設的 Leaflet 外部超連結
                }}
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; OpenStreetMap'
                }}).addTo(map);

                var marker = null;
                var polyline = null;
                var pathCoords = [];
                var eventMarkers = [];

                function updateMarker(lat, lng, follow, timeStr) {{
                    var newLatLng = new L.LatLng(lat, lng);
                    pathCoords.push([lat, lng]);

                    if (marker === null) {{
                        // 首次收到定位：建立高亮主標示點與軌跡線 (取消彈出文字框)
                        marker = L.circleMarker(newLatLng, {{
                            radius: 7,
                            color: '#FFFFFF',
                            fillColor: '#FF3B30',
                            fillOpacity: 1.0,
                            weight: 2
                        }}).addTo(map);
                        
                        polyline = L.polyline(pathCoords, {{
                            color: '#FF3B30',
                            weight: 4,
                            opacity: 0.85
                        }}).addTo(map);
                        // 首次定位：縮放到詳細層級
                        map.setView(newLatLng, 15);
                    }} else {{
                        marker.setLatLng(newLatLng);
                        polyline.setLatLngs(pathCoords);
                        if (follow) {{
                            map.panTo(newLatLng);
                        }}
                    }}

                    // 新增歷史軌跡輕量點與 hover 時間提示 Tooltip
                    var pointTooltip = (timeStr ? "[" + timeStr + "] " : "") + lat.toFixed(5) + ", " + lng.toFixed(5);
                    L.circleMarker(newLatLng, {{
                        radius: 3,
                        color: '#FF3B30',
                        fillColor: '#FF9500',
                        fillOpacity: 0.7,
                        weight: 1
                    }}).bindTooltip(pointTooltip, {{ sticky: true }}).addTo(map);
                }}

                function addEventMarker(lat, lng, labelText, color) {{
                    var eventLatLng = new L.LatLng(lat, lng);
                    var markerColor = color || '#D500F9';
                    var m = L.circleMarker(eventLatLng, {{
                        radius: 9,
                        color: '#FFFFFF',
                        fillColor: markerColor,
                        fillOpacity: 0.9,
                        weight: 2
                    }}).bindPopup("<b>" + labelText + "</b>").addTo(map);
                    eventMarkers.push(m);
                }}
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
        self.map_initialized = True
        self.current_location = location
        
    def update(self, location: Tuple[float, float], follow: bool = True, time_str: str = ""):
        """
        更新位置標記與歷史軌跡。
        
        Args:
            location (Tuple[float, float]): 新的(緯度, 經度)位置
            follow (bool): True=鏡頭自動跟隨火箭，False=只更新標記不移動視角
            time_str (str): 可選的時間戳字串 (HH:MM:SS)
        """
        if location != self.current_location:
            self.current_location = location
            if self.map_initialized:
                lat, lng = location
                follow_js = "true" if follow else "false"
                time_js = f"'{time_str}'" if time_str else "''"
                js_code = f"if (typeof updateMarker === 'function') {{ updateMarker({lat}, {lng}, {follow_js}, {time_js}); }}"
                self.web_view.page().runJavaScript(js_code)
            else:
                self.create_map(location)

    def add_event_marker(self, location: Tuple[float, float], label_text: str, color: str = "#D500F9"):
        """在地圖指定經緯度加上事件卡片標記"""
        if self.map_initialized and location:
            lat, lng = location
            # 轉義引號，防止 JS 字串截斷
            safe_label = label_text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            js_code = f"if (typeof addEventMarker === 'function') {{ addEventMarker({lat}, {lng}, '{safe_label}', '{color}'); }}"
            self.web_view.page().runJavaScript(js_code)

    def reset(self, initial_location: Tuple[float, float] = (23.5, 121.5)):
        """重置地圖與歷史軌跡線標記"""
        self.create_map(initial_location)