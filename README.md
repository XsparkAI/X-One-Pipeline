# Xspark AI X-One Platform

[![中文](https://img.shields.io/badge/中文-简体-blue)](./README_CN.md)  
[![English](https://img.shields.io/badge/English-English-green)](./README.md)

> This repository provides the usage code and complete documentation for the Xspark AI X-One platform. X-One is a robot learning platform that supports integrated master-slave control and teleoperation data collection. It integrates teaching collection, data storage, playback, and algorithm evaluation capabilities to build an end-to-end integrated workflow.
> 
> X-One URDF/USD Repository: [https://github.com/XsparkAI/X-Arm-Description](https://github.com/XsparkAI/X-Arm-Description)
>
> If you have any questions, please contact us via [X-One Q&A Lark Group](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=1f7l701d-8907-4bf2-9931-d1ec298a4abf) or WeChat `TianxingChen_2002`.

## 2. Integrated Feature Usage

### 2.1 Environmental Installation
``` bash
bash scripts/install.sh
```
After executing the script, please select the installation script according to your computer configuration. Note: if the computer does not have a ROS environment installed, you need to select (3) to configure the ROS environment first.

### 2.2 Robotic Arm CAN Port Configuration

First, go to the configuration path:
```bash
# If you are using Ubuntu 20.04
cd third_party/y1_sdk_python/y1_ros/can_scripts/
# If you are using Ubuntu 22.04
cd third_party/y1_sdk_python/y1_ros2/can_scripts/
```
Then query the current device's serial number, plugging only one robotic arm USB into the computer:
``` bash
# Note, the official script has issues; lines 3~9 need to be deleted
bash search.sh
```
The result should look like this:
``` bash
Found ttyACM device
{idVendor}=="16d0"
{idProduct}=="117e"
{serial}=="20A6358B4543"
```
Remember the `serial` number and fill it into `ATTRS{serial}==""` in `imeta_y1_can.rules`. We default the left arm to `imeta_y1_can0` and the right arm to `imeta_y1_can1`. The result will look like the image below, only the `serial` parameter is different.

```bash
SUBSYSTEM=="tty", ATTRS{idVendor}=="16d0", ATTRS{idProduct}=="117e", ATTRS{serial}=="209435684543", SYMLINK+="imeta_y1_can0"
SUBSYSTEM=="tty", ATTRS{idVendor}=="16d0", ATTRS{idProduct}=="117e", ATTRS{serial}=="209431564563", SYMLINK+="imeta_y1_can1"
```

Then write the configuration:
```bash
bash set_rules.sh
```

Finally, open the CAN port in two new terminals (can use tmux):
```bash
bash 
bash start_can0.sh

bash start_can1.sh
```
If configured successfully, the output will look like this:
```bash
can0 offline, restarting...
[sudo] password for xspark-ai: 
Cannot find device "can0"
Starting slcand...
Configuring can0 interface...
can0 started successfully
...
```

### 2.3 Data Collection

***Note!***

Before each data collection, you must confirm that your bound USB camera is correctly bound. Execute `tools/scan_camera.py` to view all connected cameras and their corresponding IDs for calibration. Place the calibrated results into the corresponding `CAMERA_SERIALS` in `config/x-one.yml`.

`task_name` defines the current task name. `collect_cfg` indexes to the `config/${collect_cfg}.yml` file, which configures parameters related to data collection, robotic arm control, terminal usage, etc. For details, refer to the [Parameter Documentation](./config/README.md). Currently, we use `x-one` as the default body. This system also supports data collection for different bodies. `--st_idx` is an optional parameter followed by the starting index, defaulting to `0`. Data is saved in `data/${collect_cfg}/${task_name}` by default.

``` bash
bash scripts/collect.sh ${task_name} ${base_cfg} # Optional: --st_idx 100
# bash scripts/collect.sh demo x-one
```

#### HTTP-based Teleoperation Data Collection

> If you have two X-One platforms and wish to use master-slave teleoperation, please follow these instructions.

This operation requires `use_node=True` in `robot_cfg`. Then select the configuration files for the master and slave arms (X-One provides the master arm configuration). Note: since the master arm does not require data collection but only high-frequency communication of joint information, cameras and other sensors are not bound to the master arm. Run `collect_teleop.sh` based on the operating parameters.

```bash
bash scripts/collect_teleop.sh ${task_name} ${master_base_cfg} ${slave_base_cfg} ${port}
# bash scripts/collect_teleop.sh teleop_sample x-one-master x-one 10001
```

### 2.4 Reset Robotic Arm Position

Currently, we use `x-one` as the default body. Running the script will drive the robotic arm to the joint position defined in `config/${collect_cfg}.yml:['robot']['init_qpos']`, which defaults to all zeros and grippers open.

``` bash
bash scripts/reset.sh ${base_cfg} 
# bash scripts/reset.sh x-one
```

### 2.5 Replay Data Trajectory

Running this script will replay a specific trajectory for a specific task and body.

``` bash
bash scripts/replay.sh ${task_name} ${base_cfg} ${idx}
# bash scripts/replay.sh demo x-one 0
```

### 2.6 Policy Deployment

To adapt a specific policy, refer to `policy_lab/replay_policy`. You need to follow this structure and implement the following files:

- `deploy.py`
- `deploy.sh`
- `${your_policy}.py`
- `eval.sh`

`deploy.yml` can be copied directly unless you need extra input parameters.

---

#### Functions to Implement in `deploy.py`

1. `get_model(deploy_cfg)`  
   - Instantiate your policy using the input `deploy_cfg`.

2. `eval_one_episode(TASK_ENV, model_client)`  
   - This function can be copied directly unless you need additional logic during inference.

---

#### Encapsulating Policy Interface in `${your_policy}.py`

You need to encapsulate your function to return the instantiated model for `get_model()` in `deploy.py`. You can modify the corresponding interface code in `demo_policy`, but **do not modify input parameters**.

1. `update_obs(obs)`  
   - No return value. Called before each inference to update the policy's observation.

2. `get_action(self, obs=None)`  
   - Defaults to `obs=None`, using only observation updated by `update_obs()`. Returns a dictionary.

3. `reset(self)`  
   - Resets model observations to avoid influence from previous rounds.

4. `set_language(self, instruction)`  
   - Optional, called in `eval_one_episode()`.

### 2.7 MIT Control Usage
***Note!***

MIT control requires updating `y1_sdk` and is currently only available on ROS1 Noetic. Manually uninstall `third_party/y1_sdk_python/` and rerunning:
```bash
bash scripts/install.sh
```

MIT protocol usage requires replacing `Y1_controller` with `Y1mit_controller`, adding joint torque information to the returned data, and supporting robotic arm control via torque.

This project provides a gravity compensation control example based on MIT, which can adapt to all end-effectors with different centers of mass and weights:
```bash
# Compile third_party/y1_mit/y1_cal.cpp into a .so file
g++ -O3 -fPIC -shared y1_cal.cpp -o libregressor.so
# Move to src/robot/controller/
cp libregressor.so ../../src/robot/controller/
# Collect trajectories for torque calculation
python -m src.robot.controller.Y1mit_controller
# Replay trajectories and calculate parameters
python -m src.robot.controller.Y1mit_controller
# Test MIT gravity compensation
python -m src.robot.controller.Y1mit_controller
```

### 2.8 (Optional) Camera Calibration
You can bind camera serial numbers on the computer so that recalibration is not needed after every reboot.

```bash
python tools/set_camera_rules.py

# Note: this is not burning; you need to repeat this after changing computers.
# Follow prompts to configure cameras, three mappings will appear, replace them in config/x-one.yml.
/dev/head_camera
/dev/left_wrist_camera
/dev/right_wrist_camera
```