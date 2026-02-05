<h1 align="center">Xspark AI X-One平台</h1>

> 本仓库提供 Xspark AI X-One 平台的使用代码与完整文档。X-One 是一个支持主从一体控制与遥操作数据采集的机器人操作学习平台，集成示教采集、数据存储、回放与算法评测能力，构建端到端的一体化工作流。
> 
> X-One相关URDF/USD仓库：[https://github.com/XsparkAI/X-Arm-Description](https://github.com/XsparkAI/X-Arm-Description)
>
> 如果有任何使用问题，欢迎通过以下联系方式进行联系【[X-One答疑飞书群](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=1f7l701d-8907-4bf2-9931-d1ec298a4abf)】或【微信联系方式 `TianxingChen_2002`】。

## 2. 集成功能使用

### 2.1 环境安装
```
bash scripts/intall.sh
```

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

```
bash scripts/collect.sh ${task_name} ${collect_cfg} # 可选：--st_idx 100
# bash scripts/collect.sh demo x-one
```

TODO：teleop，将于2026年2月6日前完善。

### 2.4 重置机械臂位置

当前我们使用`x-one`本体作为默认本体，运行脚本会驱动机械臂运动至`config/${collect_cfg}.yml:['robot']['init_qpos']`的关节位置，默认为关机全0，夹爪张开.

```
bash scripts/reset.sh ${collect_cfg} 
# bash scripts/reset.sh x-one
```

### 2.5 回放数据轨迹

运行此脚本将会回放特定任务、特定本体的特定轨迹。

```
bash scripts/replay.sh ${task_name} ${collect_cfg} ${idx}
# bash scripts/replay.sh demo x-one 0
```

### 2.6 部署策略

