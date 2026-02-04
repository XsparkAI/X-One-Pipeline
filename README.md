## 机械臂setup
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
记住serial编号, 填入到imeta_y1_can.rules中`ATTRS{serial}==""`, 我们默认左臂是imeta_y1_can0, 右臂是imeta_y1_can1.得到结果类似下图, 只有`serial`参数不同, 其他一致.

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
