# X-One Data Collection Configuration

本项目使用 YAML 配置文件来定义**X-One数据采集任务**的运行参数，包括日志等级、存储方式、采集频率、机器人初始状态、CAN 总线映射以及相机设备绑定等。

该配置主要用于控制双机械臂在**位置控制模式（position control）**下进行数据采集，并将多模态数据保存为 **HDF5** 格式。

---

## 📁 Configuration File Overview

```yaml
INFO_LEVEL: INFO          # DEBUG, INFO, ERROR

use_node: true

save_dir: ./data/dual_x_arm/
save_format: hdf5
start_episode: 0
num_episode: 5
save_freq: 30  # in Hz
move_check: false

deploy:
  force_reach: true

robot:
  type: dual_x_arm
  init_qpos: 
    left_arm: [0, 0, 0, 0, 0, 0]
    left_gripper: 1.0
    right_arm: [0, 0, 0, 0, 0, 0]
    right_gripper: 1.0
  control_mode: position
  ROBOT_CAN:
    left_arm: can1
    right_arm: can0
  CAMERA_SERIALS:
    head: "/dev/head_camera"
    left_wrist: "/dev/left_wrist_camera"
    right_wrist: "/dev/right_wrist_camera"
```

---

## 🔧 Global Parameters

| Parameter     | Type   | Description                     |
| ------------- | ------ | ------------------------------- |
| INFO_LEVEL    | string | 日志级别：`DEBUG` / `INFO` / `ERROR` |
| use_node      | bool   | 是否使用节点化架构（如 ROS/中间件）            |
| save_dir      | string | 数据保存目录                          |
| save_format   | string | 数据存储格式（当前为 `hdf5`）              |
| start_episode | int    | 起始 episode 编号                   |
| num_episode   | int    | 采集 episode 数量                   |
| save_freq     | int    | 数据保存频率（Hz）                      |
| move_check    | bool   | 是否在采集前进行运动可行性检查                 |

---

## 📦 Deploy Parameters

```yaml
deploy:
  force_reach: true
```

| Parameter   | Type | Description         |
| ----------- | ---- | ------------------- |
| force_reach | bool | 强制尝试到达目标位姿，即使存在轻微误差 |

**说明：**
开启后可提高轨迹执行的完整性，但在真实机器人上需注意安全。

---

## 🤖 Robot Configuration

### 1. Robot Type

```yaml
robot:
  type: dual_x_arm
```

表示使用**双机械臂系统（Dual X-Arm）**。

---

### 2. Initial Joint Position (init_qpos)

```yaml
init_qpos:
  left_arm: [0, 0, 0, 0, 0, 0]
  left_gripper: 1.0
  right_arm: [0, 0, 0, 0, 0, 0]
  right_gripper: 1.0
```

| Field         | Meaning  |
| ------------- | -------- |
| left_arm      | 左臂 6 关节角 |
| right_arm     | 右臂 6 关节角 |
| left_gripper  | 左夹爪张开程度  |
| right_gripper | 右夹爪张开程度  |

数值单位通常为 **弧度（rad）**，夹爪为 **归一化开合值**。

---

### 3. Control Mode

```yaml
control_mode: position
```

可选示例：

* `position` → 关节位置控制
* `velocity` → 速度控制
* `torque` → 力矩控制

---

### 4. CAN Bus Mapping

```yaml
ROBOT_CAN:
  left_arm: can1
  right_arm: can0
```

用于指定每个机械臂对应的 **CAN 接口**。

| Arm       | Interface |
| --------- | --------- |
| left_arm  | can1      |
| right_arm | can0      |

---

### 5. Camera Device Mapping

```yaml
CAMERA_SERIALS:
  head: "/dev/head_camera"
  left_wrist: "/dev/left_wrist_camera"
  right_wrist: "/dev/right_wrist_camera"
```

定义各相机在系统中的设备路径。

| Camera      | Device                  |
| ----------- | ----------------------- |
| head        | /dev/head_camera        |
| left_wrist  | /dev/left_wrist_camera  |
| right_wrist | /dev/right_wrist_camera |

---

## 📂 Output Data Structure (Example)

```
data/dual_x_arm/
 ├── episode_0000.hdf5
 ├── episode_0001.hdf5
 ├── ...
```

每个 HDF5 文件通常包含：

* joint positions
* gripper states
* camera images
* timestamps
* actions

---