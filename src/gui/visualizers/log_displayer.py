import logging
import sys
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import QObject, pyqtSignal
from datetime import datetime

class LogSignalEmitter(QObject):
    log_received = pyqtSignal(str)

class LogDisplayer:
    def __init__(self, log_widget: QTextEdit):
        self.log_widget = log_widget
        self.log_widget.setReadOnly(True)
        self.emitter = LogSignalEmitter()
        self.emitter.log_received.connect(self._append_log)
        self.setup_logging()
    
    def _append_log(self, msg: str):
        self.log_widget.append(msg)
        self.log_widget.moveCursor(QTextCursor.MoveOperation.End)

    def setup_logging(self):
        # 創建自定義處理器
        qt_handler = self.QtLogHandler(self.emitter)
        qt_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        
        # 添加到root logger
        logging.getLogger().addHandler(qt_handler)
        
        # 重定向標準輸出
        sys.stdout = self.QtOutputRedirector(self.emitter)
        sys.stderr = self.QtOutputRedirector(self.emitter)
        
    class QtLogHandler(logging.Handler):
        def __init__(self, emitter: LogSignalEmitter):
            super().__init__()
            self.emitter = emitter
            
        def emit(self, record):
            try:
                msg = self.format(record)
                self.emitter.log_received.emit(msg)
            except Exception:
                self.handleError(record)
    
    class QtOutputRedirector:
        def __init__(self, emitter: LogSignalEmitter):
            self.emitter = emitter
            
        def write(self, text):
            if text.strip():
                timestamp = datetime.now().strftime('%H:%M:%S')
                self.emitter.log_received.emit(f'[{timestamp}] {text.strip()}')
                
        def flush(self):
            pass