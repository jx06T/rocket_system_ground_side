import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer
from OpenGL import GL as gl
from OpenGL.GLU import gluPerspective


class CubeGLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 初始角度
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0

    def initializeGL(self):
        # 設定清除色與啟用深度測試
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)

    def resizeGL(self, width, height):
        # 設定檢視區域
        gl.glViewport(0, 0, width, height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        aspect = width / height if height != 0 else 1
        # 使用 gluPerspective 設定透視投影
        gluPerspective(45.0, aspect, 0.1, 100.0)
        gl.glMatrixMode(gl.GL_MODELVIEW)

    def paintGL(self):
        # 清除畫面與深度緩衝區
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glLoadIdentity()
        # 將畫面平移，以便看到立方體
        gl.glTranslatef(0.0, 0.0, -6.0)
        # 根據 pitch 與 roll 進行旋轉
        gl.glRotatef(self.pitch, 1.0, 0.0, 0.0)  # X 軸（俯仰角）
        gl.glRotatef(self.roll, 0.0, 0.0, 1.0)   # Z 軸（滾轉角）
        gl.glRotatef(self.yaw, 0.0, 1.0, 0.0) 
        self.drawCube()

    def drawCube(self):
        # 繪製一個有 6 個面的立方體，每一面使用不同顏色
        gl.glBegin(gl.GL_QUADS)
        # 前面 (Z+)
        gl.glColor3f(1.0, 0.0, 0.0)  # 紅色
        gl.glVertex3f(-1.0, -1.0,  1.0)
        gl.glVertex3f( 1.0, -1.0,  1.0)
        gl.glVertex3f( 1.0,  1.0,  1.0)
        gl.glVertex3f(-1.0,  1.0,  1.0)
        # 後面 (Z-)
        gl.glColor3f(0.0, 1.0, 0.0)  # 綠色
        gl.glVertex3f(-1.0, -1.0, -1.0)
        gl.glVertex3f(-1.0,  1.0, -1.0)
        gl.glVertex3f( 1.0,  1.0, -1.0)
        gl.glVertex3f( 1.0, -1.0, -1.0)
        # 上面 (Y+)
        gl.glColor3f(0.0, 0.0, 1.0)  # 藍色
        gl.glVertex3f(-1.0,  1.0, -1.0)
        gl.glVertex3f(-1.0,  1.0,  1.0)
        gl.glVertex3f( 1.0,  1.0,  1.0)
        gl.glVertex3f( 1.0,  1.0, -1.0)
        # 底面 (Y-)
        gl.glColor3f(1.0, 1.0, 0.0)  # 黃色
        gl.glVertex3f(-1.0, -1.0, -1.0)
        gl.glVertex3f( 1.0, -1.0, -1.0)
        gl.glVertex3f( 1.0, -1.0,  1.0)
        gl.glVertex3f(-1.0, -1.0,  1.0)
        # 右面 (X+)
        gl.glColor3f(1.0, 0.0, 1.0)  # 品紅
        gl.glVertex3f( 1.0, -1.0, -1.0)
        gl.glVertex3f( 1.0,  1.0, -1.0)
        gl.glVertex3f( 1.0,  1.0,  1.0)
        gl.glVertex3f( 1.0, -1.0,  1.0)
        # 左面 (X-)
        gl.glColor3f(0.0, 1.0, 1.0)  # 青色
        gl.glVertex3f(-1.0, -1.0, -1.0)
        gl.glVertex3f(-1.0, -1.0,  1.0)
        gl.glVertex3f(-1.0,  1.0,  1.0)
        gl.glVertex3f(-1.0,  1.0, -1.0)
        gl.glEnd()


class AttitudeDisplayer:
    def __init__(self, gl_widget: CubeGLWidget):
        self.gl_widget = gl_widget
        self.current_pitch = 0.0
        self.current_roll = 0.0
        self.current_yaw = 0.0

    def update(self, pitch: float, roll: float, yaw: float):
        """
        更新立方體的顯示角度
        :param pitch: 俯仰角
        :param roll: 滾轉角
        :param yaw: 旋轉角
        """
        if pitch == self.current_pitch and roll == self.current_roll and yaw == self.current_yaw:
            return
        self.current_pitch = pitch
        self.current_roll = roll
        self.current_yaw = yaw
        self.gl_widget.pitch = pitch
        self.gl_widget.roll = roll
        self.gl_widget.yaw = yaw 
        self.gl_widget.update()  # 通知 widget 重繪

