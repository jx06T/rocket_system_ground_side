# Rocket Attitude Configuration & Coordinate Systems Reference

This document serves as a reference for the 3-axis complementary filter, OpenGL world mapping, and sensor-to-body alignment configurations implemented in the ground station.

## 1. Coordinate Systems Definition

### A. OpenGL World Coordinate Frame (3D Viewport)
In the 3D attitude viewer (OpenGL/PyQt), the coordinate axes are defined as:
* **Y-Axis (Up, Green)**: Pointing straight UP. The longitudinal axis (length) of the rocket model is drawn along the Y-axis (body: $Y=-2.0$ to $2.0$, nose cone apex: $Y=2.6$).
* **X-Axis (Horizontal, Red)**: Pointing to the right. Rotation around this axis represents **Pitch** (tilting forward/backward).
* **Z-Axis (Depth, Blue)**: Pointing out of the screen. Rotation around this axis represents **Yaw-tilt** (tilting left/right).

### B. Standard Rocket Body Frame
* **Longitudinal Axis ($Z_{body}$)**: Aligned with the body of the rocket pointing towards the nose. Self-spin (Roll) occurs around this axis.
* **Transverse Axis 1 ($X_{body}$)**: Pitch rate/angle axis.
* **Transverse Axis 2 ($Y_{body}$)**: Yaw-tilt rate/angle axis.

---

## 2. Sensor-to-Body Axis Mapping

To support flexible sensor placement without changing bottom-level algorithms, mappings are defined in [main_window.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/main_window.py#L31-L38):
```python
self.axis_config = {
    "ax": "+ax",  # Rocket X_body (Pitch tilt) ➔ Sensor raw ax
    "ay": "+ay",  # Rocket Y_body (Yaw-tilt) ➔ Sensor raw ay
    "az": "+az",  # Rocket Z_body (Roll self-spin) ➔ Sensor raw az
    "gx": "+gx",  # Pitch rate ➔ Sensor raw gx
    "gy": "+gy",  # Yaw-tilt rate ➔ Sensor raw gy
    "gz": "+gz"   # Roll self-spin rate ➔ Sensor raw gz
}
```

### How to Adjust Sensor Orientation:
If the sensor orientation inside the rocket changes in the future, modify `self.axis_config` to re-map raw axes and reverse directions:
1. **Swap axes**: Change the string keys (e.g. `"ay": "+az"`, `"az": "+ay"`).
2. **Reverse direction**: Flip the sign (e.g. `"gz": "-gy"`).
The mapping helper `_get_mapped_axis` automatically resolves signs and parses properties dynamically.

---

## 3. Mathematical Coordinate Fusion (Cross-Axis Coupling)

In 3D space, gravity acceleration and angular rates exhibit cross-axis relations when the rocket is vertical:
* **Pitch (tilt around X-axis)**: Pitch rate is driven by `gx` (X-gyro). However, pitch tilt relative to gravity is measured by Y-acceleration (`ay`, or `body_roll_acc`).
* **Yaw-tilt (tilt around Z-axis)**: Yaw rate is driven by `gy` (Y-gyro). Tilt relative to gravity is measured by X-acceleration (`ax`, or `-body_pitch_acc`).
* **Self-spin (Roll, rotation around Y-axis)**: Self-spin rate is driven by `gz` (Z-gyro). Gravity cannot measure spin when vertical; direction is corrected via compass/GPS if available.

### Gyro Bias Calibration (Zero-offset):
Calibration averages the last 100 frames of static gyro measurements to define `self.gyro_bias_x/y/z` offsets. These offsets are dynamically subtracted from the mapped gyro measurements before filter updates to eliminate long-term yaw drift.

### Adaptive Complementary Filter:
To prevent dynamic linear accelerations (from vibrations, movement, or engine boost) from corrupting the gravity vector tilt calculation, an adaptive weight factor is used.
* **Acceleration Deviation**: $D_{acc} = |A_{total} - 1.0g|$ where $A_{total} = \sqrt{ax^2 + ay^2 + az^2}$.
* **Adaptive Weight Calculation**:
  * If $D_{acc} < 0.08g$: $\alpha = 0.05$ (trust accelerometer fully).
  * If $D_{acc} > 0.25g$: $\alpha = 0.0$ (ignore accelerometer, trust pure gyro integration to avoid tilt distortion).
  * If in between: $\alpha$ is linearly scaled down.

```python
# 1. Pitch (X-rotation) corrects with Y-acceleration (body_roll_acc)
self.est_pitch = (1 - alpha) * (self.est_pitch + gx * dt) + alpha * body_roll_acc

# 2. Yaw-tilt (Z-rotation) corrects with X-acceleration (-body_pitch_acc)
self.est_roll = (1 - alpha) * (self.est_roll - gy * dt) - alpha * body_pitch_acc

# 3. Self-spin/Yaw (Y-rotation) integrates Z-gyro (gz)
self.est_yaw = (self.est_yaw + gz * dt) % 360  # (or corrected by compass direction)
```

---

## 4. 3D Model Quaternion Alignment

To map estimated filter angles to OpenGL rotations, they are combined in the ZYX Euler sequence inside `handle_angle_change`:
```python
self.quaternion = self.handle_angle_change(self.est_pitch, self.est_yaw, self.est_roll)
```
Inside [main_window.py](file:///d:/Document_J/code/rocket_system_ground_side/src/gui/main_window.py#L276-L290):
1. **Y-axis rotation (Y-rotation)**: `spin_q = euler_to_quaternion(roll, 0, 0)` rotates `self.est_yaw` (heading/spin).
2. **X-axis rotation (X-rotation)**: `pitch_q = euler_to_quaternion(0, pitch, 0)` rotates `self.est_pitch` (Pitch tilt).
3. **Z-axis rotation (Z-rotation)**: `yaw_q = euler_to_quaternion(0, 0, yaw)` rotates `self.est_roll` (Yaw-tilt).

This ZYX combo guarantees correct static launchpad tilt and dynamic flight rotation without axis drift or upside-down flipping.
