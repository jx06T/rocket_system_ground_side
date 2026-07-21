import sys
import os
import time
import logging
import subprocess
import argparse
import socket
import uuid
from datetime import datetime
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.utils.settings import load_channel_settings, list_channel_ids

def setup_logging(timestamp: str, run_id: str):
    # 確保日誌目錄存在
    os.makedirs("logs", exist_ok=True)
    # 創建基礎配置，包含時間戳與 Session ID 以維持命名統一
    log_filename = f"logs/app_{timestamp}_{run_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            # 同時輸出到文件和控制台
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 獲取 root logger
    logger = logging.getLogger()
    logger.info("Logging system initialized")
    
def main():
    run_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    setup_logging(timestamp, run_id)

    # 解析命令列參數 (使用 parse_known_args 避免干擾 PyQt6 的參數)
    parser = argparse.ArgumentParser(description="Ground Station GUI Launcher")
    parser.add_argument("--gui-only", action="store_true", help="Launch GUI only without spawning any backend daemon")
    args, unknown = parser.parse_known_args()

    # ── 雙板熱備援: 取得所有通道 (ch1=915MHz/E22, ch2=2.4GHz/E28) ──
    channel_ids = list_channel_ids()          # e.g. ["ch1", "ch2"]
    logging.info(f"Configured telemetry channels (hot-standby): {channel_ids}")

    def _port_in_use(port: int) -> bool:
        # 不設 SO_REUSEADDR: Windows 下會讓測試 bind 誤判為「可用」
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    def is_backend_running(channel_id: str) -> bool:
        """該通道任一 ZMQ 埠被佔用 => 其後端 daemon 已在執行。"""
        _, _, zp, zcp = load_channel_settings(channel_id)
        return _port_in_use(zp) or _port_in_use(zcp)

    backend_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "backend_daemon.py")
    backend_processes = []   # list of (channel_id, Popen)

    if args.gui_only:
        logging.info("GUI-only mode: skipping ALL backend spawns. GUI will attach to pre-running daemons "
                     "(start them via run_persist_backend.bat).")
    else:
        for ch in channel_ids:
            if is_backend_running(ch):
                logging.warning(f"⚠ [{ch}] ZMQ ports already in use -> a daemon is ALREADY running; "
                                f"attaching instead of spawning. (Stale daemon? kill it if telemetry looks wrong.)")
                continue
            logging.info(f"[{ch}] Spawning backend daemon: {backend_script} --channel {ch}")
            try:
                # 各自獨立 stdin pipe -> 各自 self-destruct 綁定 main.py 生命週期
                p = subprocess.Popen(
                    [sys.executable, backend_script, "--channel", ch],
                    stdin=subprocess.PIPE,
                    stdout=None,   # 保留標準輸出供調試
                    stderr=None,
                )
                backend_processes.append((ch, p))
            except Exception as e:
                # 一板 spawn 失敗不可讓另一板也起不來 -> 記錄後繼續, 不 sys.exit
                logging.error(f"❌ [{ch}] Failed to spawn backend daemon: {e}")

        # ── 就緒檢查 (安全關鍵): 每板 CMD 埠須在 timeout 內綁定, 否則 /dpl_all 對該板逾時 ──
        _deadline = time.time() + 4.0
        pending = set(channel_ids)
        while pending and time.time() < _deadline:
            for ch in list(pending):
                _, _, _, _zcp = load_channel_settings(ch)
                if _port_in_use(_zcp):     # REP 已綁定 => 可收命令
                    pending.discard(ch)
            if pending:
                time.sleep(0.1)
        for ch in pending:
            logging.error(f"🔴 [{ch}] backend command port NOT bound after 4s — remote commands to this "
                          f"board WILL FAIL. Check its COM port and the daemon console for a Python error.")


    try:
        # 設置共享 OpenGL 上下文，避免 WebEngine 與 OpenGL 視窗產生資源衝突與虛擬化錯誤警告
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
        app = QApplication(sys.argv)

        # 啟動 GUI (傳入所有通道 -> 訂閱兩板遙測 + /dpl_all 廣播兩板)
        logging.info("Creating main window...")
        window = MainWindow(channel_ids)
        window.show()

        app.exec()
    except Exception as e:
        logging.exception("FATAL ERROR IN GUI INITIATION OR RUNTIME:")
        sys.exit(1)
    finally:
        # 各 daemon 獨立收尾: 一個卡住不擋另一個
        for ch, p in backend_processes:
            if p is None:
                continue
            logging.info(f"[{ch}] GUI exited. Terminating backend daemon (pid={p.pid})...")
            try:
                # 先關 stdin -> 觸發 daemon self-destruct watcher; 再 terminate 保險
                try:
                    if p.stdin:
                        p.stdin.close()
                except Exception:
                    pass
                p.terminate()
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logging.warning(f"[{ch}] Backend daemon did not terminate in time. Killing it...")
                p.kill()
            except Exception as ex:
                logging.error(f"[{ch}] Error cleaning up backend process: {ex}")

if __name__ == "__main__":
    main()
