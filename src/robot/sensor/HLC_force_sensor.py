from robot.sensor.base_touch_sensor import BaseTouchSensor
from robot.utils.base.data_handler import debug_print
from robot.utils.extra.HLC_force6d import SensorConnector, SensorType, CommucationProtocol

class HLCForceSensor(BaseTouchSensor):
    def __init__(self, TEST=False):
        super().__init__(TEST)
        self.name = "HLC_force_sensor"
    
    def set_up(self, device_index=''):
        self.sensor= SensorConnector(CommucationProtocol.AT_Command, SensorType.PHOTON_FINGER, device_index, 115200)

        if not self.sensor.Connect():
            raise RuntimeError(f"Failed to connect to HLC force sensor at {device_index}")

        ## 设置获取数据的间隔时长 0.02秒
        self.sensor.set_read_break(0.02)  

        # 循环读取和处理数据
        ok,resp = self.sensor.sendCommand("AT+SZERO=1")
        
    def get_force(self):
        ret_data ={}
        data= self.sensor.GetData()
        
        if(data is not None):
            Fz = data.get('Fz', None)
            Mx = data.get('Mx', None)
            My = data.get('My', None)
            Fx,Fy,Fz,Mx,My = self.sensor.finger_series_decouple(0,0,2.5,Fz,Mx,My)

        ret_data["force6d"] = [Fx,Fy,Fz,Mx,My, 0.0]

        return ret_data

if __name__ == "__main__":
    sensor = HLCForceSensor()
    sensor.set_up("/dev/left_force_sensor")
    print("success!")

    try:
        while True:
            force_data = sensor.get_force()
            print(force_data)
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Shutting down...")
    finally:
        sensor.sensor.Close()