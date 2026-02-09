<h1 align="center">Xspark AI X-One平台</h1>

> 本仓库提供 Xspark AI X-One 平台的使用代码与完整文档。X-One 是一个支持主从一体控制与遥操作数据采集的机器人操作学习平台，集成示教采集、数据存储、回放与算法评测能力，构建端到端的一体化工作流。
> 
> X-One相关URDF/USD仓库：[https://github.com/XsparkAI/X-Arm-Description](https://github.com/XsparkAI/X-Arm-Description)
>
> 如果有任何使用问题，欢迎通过以下联系方式进行联系【[X-One答疑飞书群](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=1f7l701d-8907-4bf2-9931-d1ec298a4abf)】或【微信联系方式 `TianxingChen_2002`】。

## 2. 集成功能使用

### 2.1 环境安装
``` bash
bash scripts/install.sh
```
执行脚本后请根据提示选择你电脑配置所要安装的脚本, 注意, 如果电脑没有安装ros环境, 则需要先选择(3)配置ros环境.

### 2.2 机械臂can口配置

首先到达配置路径:
```bash
# 如果你是ubuntu20.04, 路径在这
cd third_party/y1_sdk_python/y1_ros/can_scripts/
# 如果是ubuntu22.04, 路径在这
cd third_party/y1_sdk_python/y1_ros2/can_scripts/
```
然后查询当前设备的序列号, 只插一个机械臂的usb到电脑上:
``` bash
# 注意, 官方脚本有问题, 需要删除掉3~9行
bash search.sh
```
获取结果类似如下:
``` bash
Found ttyACM device
{idVendor}=="16d0"
{idProduct}=="117e"
{serial}=="20A6358B4543"
```
记住`serial`编号, 填入到imeta_y1_can.rules中`ATTRS{serial}==""`, 我们默认左臂是imeta_y1_can0, 右臂是imeta_y1_can1.得到结果类似下图, 只有`serial`参数不同, 其他一致.

```bash
SUBSYSTEM=="tty", ATTRS{idVendor}=="16d0", ATTRS{idProduct}=="117e", ATTRS{serial}=="209435684543", SYMLINK+="imeta_y1_can0"
SUBSYSTEM=="tty", ATTRS{idVendor}=="16d0", ATTRS{idProduct}=="117e", ATTRS{serial}=="209431564563", SYMLINK+="imeta_y1_can1"
```

然后写入配置:
```bash
bash set_rules.sh
```

最后, 在两个新的终端(可以用tmux)中, 开启can口:
```bash
bash 
bash start_can0.sh

bash start_can1.sh
```
如果配置成功, 会变成下面的输出:
```bash
can0 掉线，重启中...
[sudo] xspark-ai 的密码： 
Cannot find device "can0"
启动 slcand...
配置 can0 接口...
can0 启动成功
can0 启动成功
can0 启动成功
can0 启动成功
```

### 2.3 数据采集

`task_name`定义了当前的任务名。`collect_cfg`索引至`config/${collect_cfg}.yml`文件，配置了与数据采集、机械臂控制、终端使用等相关功能的参数，关于参数的细节内容可以通过【[参数文档](./config/README.md)】了解，当前我们使用`x-one`本体作为默认本体，此系统也可以支持不同本体的数据采集。`--st_idx`是可选参数，后面跟上开始采集的索引，默认是`0`。数据默认会保存在`data/${collect_cfg}/${task_name}`中。

``` bash
bash scripts/collect.sh ${task_name} ${base_cfg} # 可选：--st_idx 100
# bash scripts/collect.sh demo x-one
```

#### 基于HTTP通讯的遥操数采

> 当你拥有两套X-One平台并希望使用主从遥操时，请关注此指令

该操作需要`robot_cfg`中开启`use_node=True`, 然后选择主臂与从臂的配置文件(X-One已经提供了主臂的配置), 注意, 由于主臂不需要进行数据采集, 只需要高频通讯机械臂关节信息, 所以我们主臂中并未绑定摄像头等传感器. 然后根据运行参数, 执行`collect_teleop.sh`.

```bash
bash scripts/collect_teleop.sh ${task_name} ${master_base_cfg} ${slave_base_cfg} ${port}
# bash scripts/collect_teleop.sh teleop_sample x-one-master x-one 10001
```

### 2.4 重置机械臂位置

当前我们使用`x-one`本体作为默认本体，运行脚本会驱动机械臂运动至`config/${collect_cfg}.yml:['robot']['init_qpos']`的关节位置，默认为关机全0，夹爪张开.

``` bash
bash scripts/reset.sh ${base_cfg} 
# bash scripts/reset.sh x-one
```

### 2.5 回放数据轨迹

运行此脚本将会回放特定任务、特定本体的特定轨迹。

``` bash
bash scripts/replay.sh ${task_name} ${base_cfg} ${idx}
# bash scripts/replay.sh demo x-one 0
```

### 2.6 部署策略

要适配指定策略，可以参考 `policy_lab/replay_policy`。  
你需要模仿此结构，实现以下文件：

- `deploy.py`
- `deploy.sh`
- `${your_policy}.py`
- `eval.sh`

其中 `deploy.yml` 可以直接复制，除非你需要额外输入参数。

---

#### 在 `deploy.py` 中需要实现两个函数

1. `get_model(deploy_cfg)`  
   - 通过输入的 `deploy_cfg` 实例化你的策略。

2. `eval_one_episode(TASK_ENV, model_client)`  
   - 这个函数可以直接复制，不需要改动，除非你在推理阶段需要加入其他逻辑。

---

#### 在 `${your_policy}.py` 中封装策略接口

你需要将你的函数封装，用来给 `deploy.py` 的 `get_model()` 返回实例化模型。  
你可以修改 `demo_policy` 中的对应接口的代码，但**不能修改输入参数**。

1. `update_obs(obs)`  
   - 无需返回值。  
   - 每次执行推理前，会调用该函数更新策略的 observation。  
   - 可在此添加处理逻辑，方便在 `get_action()` 中使用。

2. `get_action(self, obs=None)`  
   - 默认不输入 `obs`（置为 `None`），只用 `update_obs()` 更新的 observation 来进行推理。  
   - 需要返回一个 dictionary，可参考 `your_policy.py` 中的实现。

3. `reset(self)`  
   - 重置模型的 observation，避免新一轮推理受到上一轮影响。  
   - 如果无需处理，可以直接 `return`。

4. `set_language(self, instruction)`  
   - 可不实现，仅在 `eval_one_episode()` 中选择性调用。  
   - 可类似实现其他函数，用来实现完整推理流程。
