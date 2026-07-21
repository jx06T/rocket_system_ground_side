# Implementation Plan - Decoupled Multi-Process Telemetry Architecture

This plan refactors the Ground Station from a single-process threaded model to a decoupled multi-process architecture using **ZeroMQ (ZMQ)** for IPC. This ensures the GUI rendering and crashes never affect telemetry storage (CSV & raw logs) and prepares the system for future dual-channel expansion.

---

## Goal Description
1. **Decouple GUI & Backend**:
   - The Serial port read/write and parser will run in a standalone background process (`backend_daemon.py`).
   - The GUI will run as a separate PyQt6 process (`main_gui.py` or launched via `main.py`).
   - Communication between processes will use **ZMQ PUB/SUB** for telemetry data streams.
2. **Control Backchannel (REQ/REP)**:
   - GUI controls serial settings (like port/baudrate changes) by sending JSON commands to the backend daemon over **ZMQ REQ/REP** with strict timeouts.
3. **Data Safety**:
   - Save incoming raw bytes immediately to a `.log` file before attempting any parsing.
4. **Stale Data Monitoring**:
   - Implement a heartbeat monitor in the GUI using a 5Hz `QTimer` to detect if the telemetry source has stopped updating.
5. **Timeline Alignment**:
   - Ground station timestamps (`gs_timestamp` generated on receipt) will be used for the line chart time axis.
6. **Launcher Integration**:
   - Refactor `main.py` to act as an orchestrator that launches both the backend daemon and GUI, and terminates the daemon cleanly on GUI exit.

---

## User Review Required
No breaking user-facing visual modifications will be made at this stage (such as displaying the second channel or difference widgets). Only the underlying architecture is modernized to be 100% ready for dual-channel addition.

---

## Proposed Changes

### Configuration
#### [MODIFY] [settings.py](file:///d:/Document_J/code/rocket_system_ground_side/src/utils/settings.py)
* Refactor to load/save channel-specific configurations:
  - Add channel-based configuration schema in `settings.json`.
  - Maintain compatibility wrappers for `load_settings()` and `save_settings()` mapping to `ch1`.
  - Implement `load_channel_settings(channel_id)` and `save_channel_settings(channel_id, port, baudrate)`.

#### [MODIFY] [requirements.txt](file:///d:/Document_J/code/rocket_system_ground_side/requirements.txt)
* Append `pyzmq` to the project dependencies.

---

### Backend Service (Data & Telemetry Daemon)
#### [NEW] [backend_daemon.py](file:///d:/Document_J/code/rocket_system_ground_side/src/backend_daemon.py)
* Implements the standalone backend runner:
  - Accept arguments: `--channel <ch1|ch2>` (defaults to `ch1`).
  - Read port/baudrate from channel configuration.
  - Setup raw telemetry logging: Appends raw bytes directly to `raw_<channel_id>_<date>.log` immediately inside the reader thread.
  - Setup ZMQ PUB Socket: Bind to `tcp://127.0.0.1:<zmq_port>` (CH1: `5555`, CH2: `5556`). Publish multipart messages: `[topic.encode(), json_payload]`.
  - Setup ZMQ REP Socket: Bind to `tcp://127.0.0.1:<zmq_cmd_port>` (CH1: `5565`, CH2: `5566`) to handle remote instructions (`set_port`, `set_baud`, `reconnect`, `disconnect`).

---

### Frontend Visualizer (GUI)
#### [NEW] [zmq_receiver.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/zmq_receiver.py)
* Implements `ZmqReceiverThread(QThread)`:
  - Connects to all active ZMQ PUB ports.
  - Receives multipart messages asynchronously and emits `data_received(str, dict)`.

#### [MODIFY] [main_window.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/main_window.py)
* Replace direct dependency on `SerialCommunicator` with `ZmqReceiverThread`.
* Connect ZMQ signals to `update_ui`.
* Replace `on_enter_pressed` commands (`/port`, `/baud`, etc.) with non-blocking ZMQ REQ messages using `zmq.RCVTIMEO` (1000ms timeout) to avoid UI freezing.
* Implement a 5Hz `QTimer` heartbeat monitor that updates `self.rx_led` status (Active: green, Stale: blinking orange, Disconnected: red).
* Refactor chart time plotting to use ground station arrival timestamps relative to start time.

---

### Process Orchestrator (Launcher)
#### [MODIFY] [main.py](file:///d:/Document_J/code/rocket_system_ground_side/main.py)
* Act as the orchestrator:
  - Spawns `src/backend_daemon.py` for `ch1` as a background process.
  - Runs the PyQt6 main loop.
  - Automatically terminates the backend process on exit.

---

## Verification Plan

### Automated Tests
* Run unit tests to verify parsing functionality remains intact:
  ```powershell
  python -m unittest test/test_telemetry.py
  ```

### Manual Verification
1. Run the system via `python main.py`.
2. Generate mock telemetry using `python test/mock_telemetry_generator.py`.
3. Verify that:
   - Data is plotted correctly on the charts.
   - Ground station arrival time is used for plot alignment.
   - Raw bytes are written to `raw_ch1_<date>.log` in real time.
   - Parsed records are written to `all_data_sensor.csv`.
4. Enter `/port COM33` in the GUI command line:
   - Verify that the command is successfully routed via ZMQ REQ/REP to the backend.
   - Verify that the backend attempts to reconnect on the new port.
5. Terminate the GUI forcefully (e.g. close the terminal or kill process):
   - Verify that the backend daemon is successfully stopped.
   - Verify that the raw files and CSV outputs are flushed and intact.
