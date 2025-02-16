import logging
import sys
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor
from datetime import datetime

class LogDisplayer:
    def __init__(self, log_widget: QTextEdit):
        self.log_widget = log_widget
        self.log_widget.setReadOnly(True)
        self.setup_logging()
    
    def setup_logging(self):
        # 創建自定義處理器
        qt_handler = self.QtLogHandler(self.log_widget)
        qt_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # 添加到root logger
        logging.getLogger().addHandler(qt_handler)
        
        # 重定向標準輸出
        sys.stdout = self.QtOutputRedirector(self.log_widget)
        sys.stderr = self.QtOutputRedirector(self.log_widget)
        
    class QtLogHandler(logging.Handler):
        def __init__(self, text_widget: QTextEdit):
            super().__init__()
            self.text_widget = text_widget
            
        def emit(self, record):
            msg = self.format(record)
            self.text_widget.append(msg)
            self.text_widget.moveCursor(QTextCursor.MoveOperation.End)
    
    class QtOutputRedirector:
        def __init__(self, text_widget: QTextEdit):
            self.text_widget = text_widget
            
        def write(self, text):
            if text.strip():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.text_widget.append(f'[{timestamp}] {text.strip()}')
                self.text_widget.moveCursor(QTextCursor.MoveOperation.End)
                
        def flush(self):
            pass