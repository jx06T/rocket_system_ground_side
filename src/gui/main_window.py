from PyQt6.QtWidgets import QApplication, QMainWindow ,QGraphicsScene
from ui_main import Ui_MainWindow  

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # 控制 QListWidget
        self.ui.listWidget.clear()  # 清空列表
        self.ui.listWidget.addItem("新項目")  # 新增項目
        
        # 控制 QLabel
        self.ui.label.setText("新的標籤文字")
        self.ui.label_2.setText("第二個標籤")
        self.ui.label_3.setText("第三個標籤")
        
        # 控制 QGraphicsView
        scene = QGraphicsScene()
        # 在 scene 中添加圖形
        scene.addRect(0, 0, 100, 100)
        self.ui.graphicsView.setScene(scene)
        
        # 控制 OpenGL Widget
        # 需要繼承 QOpenGLWidget 並實作相關方法
        
if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()