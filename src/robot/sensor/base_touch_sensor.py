from robot.sensor.sensor import Sensor
import numpy as np
from robot.utils.base.data_handler import debug_print

class BaseTouchSensor(Sensor):
    def __init__(self, TEST=False):
        super().__init__()
        self.name = "touch_sensor"
        self.type = "touch_sensor"
        self.collect_info = None

    def get_information(self):
        force_info = {}
        try:
            force = self.get_force()
        except Exception as e:
            debug_print(self.name, f"Pipe break: {e}", "ERROR")
            force_info = {}
            force_info["force6d"] = None
        
        if "force6d" in self.collect_info:
            force_info["force6d"] = force["force6d"]
        if "forcemap" in self.collect_info:
            force_info["forcemap"] = force["forcemap"]
        
        if "timestamp" in force.keys():
            force_info["timestamp"] = force["timestamp"]
        
        return force_info