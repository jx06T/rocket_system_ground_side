# Custom Workspace Rules for Ground Station Telemetry & Attitude

This directory contains workspace-specific rules and guidelines for assistants working on this ground station repository.

## 3D Attitude Display & Coordinate Mapping
* **Central Configuration**: Always define sensor axis maps in `self.axis_config` inside `MainWindow.__init__`. Do not hardcode coordinate flips or swaps in the core filtering algorithms.
* **Complementary Filter Pairing**: Ensure Pitch (X-rotation) is paired with Y-acceleration (`body_roll_acc`) and Yaw-tilt (Z-rotation) is paired with X-acceleration (`-body_pitch_acc`) to respect cross-axis physics.
* **OpenGL Rotation Convention**: Direct all 3D viewport rotations through `handle_angle_change(pitch, roll, yaw)`. Refer to the mapping conventions detailed in [attitude_config.md](file:///d:/Document_J/code/rocket_system_ground_side/doc/attitude_config.md) to prevent axis cross-swapping or upside-down display bugs.
* **Static Calibration**: Static calibration (`/reset-angle`) must calculate the ground gravity alignment directly and snap `est_pitch` and `est_roll` to the accelerometer targets without subtracting offsets, keeping Y-rotation (Yaw/self-spin) centered at 180.0.
