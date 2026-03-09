import sys
from robot.utils.base.footpedal import FootPedal
import time

device_path = sys.argv[1] if len(sys.argv) > 1 else "/dev/pedal"
footpedal = FootPedal(device_path)

while not footpedal.was_pressed():
    print("等待踏板按下...")
    time.sleep(0.1)
print("踏板已按下！")