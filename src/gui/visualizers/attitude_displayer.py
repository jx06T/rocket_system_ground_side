import numpy as np
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL import GL as gl
from OpenGL.GLU import gluPerspective
from src.gui.visualizers.visualization_tools import quaternion_to_matrix
class CubeGLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])  # w, x, y, z
        
    def initializeGL(self):
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        
    def resizeGL(self, width, height):
        gl.glViewport(0, 0, width, height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        aspect = width / height if height != 0 else 1
        gluPerspective(45.0, aspect, 0.1, 100.0)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        
    def paintGL(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glLoadIdentity()
        gl.glTranslatef(0.0, 0.0, -6.0)
        
        # 使用當前四元數生成旋轉矩陣
        rotation_matrix = quaternion_to_matrix(self.quaternion)
        gl.glMultMatrixf(rotation_matrix.T)
        
        self.drawCube()
        
    def drawCube(self):
        # [保持原有的drawCube代碼不變]
        gl.glBegin(gl.GL_QUADS)
        # 前面 (Z+)
        gl.glColor3f(0.3, 0.7, 0.3)  
        gl.glVertex3f(-1.0, -0.3,  1.0)
        gl.glVertex3f( 1.0, -0.3,  1.0)
        gl.glVertex3f( 1.0,  0.3,  1.0)
        gl.glVertex3f(-1.0,  0.3,  1.0)
        # 後面 (Z-)
        gl.glColor3f(0.95, 0.8, 0.1)  
        gl.glVertex3f(-1.0, -0.3, -1.0)
        gl.glVertex3f(-1.0,  0.3, -1.0)
        gl.glVertex3f( 1.0,  0.3, -1.0)
        gl.glVertex3f( 1.0, -0.3, -1.0)
        # 上面 (Y+)
        gl.glColor3f(0.7, 0.3, 0.3) 
        gl.glVertex3f(-1.0,  0.3, -1.0)
        gl.glVertex3f(-1.0,  0.3,  1.0)
        gl.glVertex3f( 1.0,  0.3,  1.0)
        gl.glVertex3f( 1.0,  0.3, -1.0)
        # 底面 (Y-)
        gl.glColor3f(0.3, 0.3, 0.7) 
        gl.glVertex3f(-1.0, -0.3, -1.0)
        gl.glVertex3f( 1.0, -0.3, -1.0)
        gl.glVertex3f( 1.0, -0.3,  1.0)
        gl.glVertex3f(-1.0, -0.3,  1.0)
        # 右面 (X+)
        gl.glColor3f(0.7, 0.7, 0.7)  
        gl.glVertex3f( 1.0, -0.3, -1.0)
        gl.glVertex3f( 1.0,  0.3, -1.0)
        gl.glVertex3f( 1.0,  0.3,  1.0)
        gl.glVertex3f( 1.0, -0.3,  1.0)
        # 左面 (X-)
        gl.glColor3f(0.8, 0.8, 0.8)  
        gl.glVertex3f(-1.0, -0.3, -1.0)
        gl.glVertex3f(-1.0, -0.3,  1.0)
        gl.glVertex3f(-1.0,  0.3,  1.0)
        gl.glVertex3f(-1.0,  0.3, -1.0)
        gl.glEnd()

class AttitudeDisplayer:
    def __init__(self, gl_widget: CubeGLWidget):
        self.gl_widget = gl_widget
        self.current_quaternion = np.array([1.0, 0.0, 0.0, 0.0])  # w, x, y, z
        
    def update(self, quaternion):
        """
        更新立方體的顯示角度
        :param quaternion # w, x, y, z
        """
        
        self.gl_widget.quaternion = quaternion / np.linalg.norm(quaternion)
        self.current_quaternion = quaternion
        
        # 重繪
        self.gl_widget.update()