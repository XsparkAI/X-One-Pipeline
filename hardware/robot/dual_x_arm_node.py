from hardware.robot.base_robot import Robot
from hardware.utils.base.data_transform_pipeline import diff_freq_pipeline
from hardware.utils.base.data_handler import is_enter_pressed, debug_print, dict_to_list
import time
from hardware.utils.node.node import TaskNode
from hardware.utils.node.scheduler import Scheduler

from threading import Lock, Event
import time

from hardware.robot.dual_x_arm import Dual_X_Arm

ROBOT_MAP = {
    "sensor": {
        "image": 30,
    },
    "controller": {
        "arm": 120,
    }
}

class DataBuffer:
    def __init__(self, start_event):
        self._buffer = {}
        self.show_buffer = {}
        self.lock = Lock()
        self.start_event= start_event

    def update(self, name, data):
        self.show_buffer[name] = data
    
    def get_lastest(self):
        return self.show_buffer

    def push(self):
        if self.start_event.is_set():
            with self.lock:
                for name, data in self.show_buffer.items():
                    if name in self._buffer.keys():
                        for k,v in data.items():
                            self._buffer[name][k].append(v)
                    else:
                        self._buffer[name] = data
                        for k,v in self._buffer[name].items():
                            self._buffer[name][k] = [v]

    def get(self):
        with self.lock:
            try:
                ret = dict_to_list(self._buffer)
            except:
                print("ERROR OCCURED!")
                import pdb;pdb.set_trace()
                exit()
            return ret
    
    def clear(self):
        with self.lock:
            self._buffer = {}

class ComponentNode(TaskNode):
    def task_init(self, component, data_buffer: DataBuffer):
        self.component = component
        self.data_buffer = data_buffer
    
    def task_step(self):
        data = self.component.get()

        self.data_buffer.update(self.component.name, data)

class DataNode(TaskNode):
    def task_init(self, data_buffer: DataBuffer):
        self.data_buffer = data_buffer
    
    def task_step(self):
        self.data_buffer.push()

def init(robot: Robot):
    start_event = Event()

    sensor_data_buffers = {}
    sensor_nodes = {}
    sensor_data_nodes = {}
    for sensor_type in ROBOT_MAP["sensor"].keys():
        sensor_nodes[sensor_type] = []
        sensor_data_buffers[sensor_type] = DataBuffer(start_event)
        sensor_data_nodes[sensor_type] = [DataNode(f"{sensor_type}_data_node", data_buffer=sensor_data_buffers[sensor_type])]

        for sensor_name, sensor in robot.sensors[sensor_type].items():
            sensor_node = ComponentNode(sensor_name, component=sensor, data_buffer=sensor_data_buffers[sensor_type])
            sensor_node.next_to(sensor_data_nodes[sensor_type][0])
            sensor_node.start()
            sensor_nodes[sensor_type].append(sensor_node)
        
        sensor_data_nodes[sensor_type][0].start()

    controller_data_buffers = {}
    controller_nodes = {}
    controller_data_nodes = {}
    for controller_type in ROBOT_MAP["controller"].keys():
        controller_nodes[controller_type] = []
        controller_data_buffers[controller_type] = DataBuffer(start_event)
        controller_data_nodes[controller_type] = [DataNode(f"{controller_type}_data_node", data_buffer=controller_data_buffers[controller_type])]

        for controller_name, controller in robot.controllers[controller_type].items():
            controller_node = ComponentNode(controller_name, component=controller, data_buffer=controller_data_buffers[controller_type])
            controller_node.next_to(controller_data_nodes[controller_type][0])
            controller_node.start()
            controller_nodes[controller_type].append(controller_node)
        
        controller_data_nodes[controller_type][0].start()

    
    return sensor_data_buffers, sensor_nodes, sensor_data_nodes, controller_data_buffers, controller_nodes, controller_data_nodes, start_event

def build_map(sensor_nodes, sensor_data_nodes, controller_nodes, controller_data_nodes):
    sensor_schedulers = {}
    for sensor_type in ROBOT_MAP["sensor"].keys():
        all_sensor_nodes: list[TaskNode] = (
            sensor_nodes[sensor_type] +
            sensor_data_nodes[sensor_type]
        )
        
        sensor_schedulers[sensor_type] = Scheduler(entry_nodes=sensor_nodes[sensor_type], 
                                                    all_nodes=all_sensor_nodes,
                                                    final_nodes=sensor_data_nodes[sensor_type],
                                                    hz=ROBOT_MAP["sensor"][sensor_type])
    controller_schedulers = {}
    for controller_type in ROBOT_MAP["controller"].keys():
        all_controller_nodes: list[TaskNode] = (
            controller_nodes[controller_type] +
            controller_data_nodes[controller_type]
        )

        controller_schedulers[controller_type] = Scheduler(entry_nodes=controller_nodes[controller_type], 
                                                    all_nodes=all_controller_nodes,
                                                    final_nodes=controller_data_nodes[controller_type],
                                                    hz=ROBOT_MAP["controller"][controller_type])
    
    return sensor_schedulers, controller_schedulers

class Dual_X_Arm_Node(Dual_X_Arm):
    def __init__(self, config, start_episode=0):
        super().__init__(config=config, start_episode=start_episode)
        self.collection._add_data_transform_pipeline(diff_freq_pipeline)

    def set_up(self, teleop=False):
        super().set_up(teleop=teleop)
        self.sensor_data_buffers, self.sensor_nodes, self.sensor_data_nodes, self.controller_data_buffers, self.controller_nodes, self.controller_data_nodes, self.start_event = init(self)

        self.sensor_schedulers,self. controller_schedulers = build_map(self.sensor_nodes, self.sensor_data_nodes, self.controller_nodes, self.controller_data_nodes)

        for sensor_scheduler in self.sensor_schedulers.values():
            sensor_scheduler.start()
        
        for controller_scheduler in self.controller_schedulers.values():
            controller_scheduler.start()

    def get(self):
        controller_data = {}
        for controller_data_buffer in self.controller_data_buffers.values():
            data = controller_data_buffer.get_lastest()
            for k, v in data.items():
                controller_data[k] = v

        sensor_data = {}
        for sensor_data_buffer in self.sensor_data_buffers.values():
            data = sensor_data_buffer.get_lastest()
            for k, v in data.items():
                sensor_data[k] = v
        return controller_data.copy(), sensor_data.copy()

    def start(self): 
        self.start_event.set()       
        debug_print("collect_node", "Collect data start!", "INFO")
    
    def clean(self):
        for sensor_data_buffer in self.sensor_data_buffers.values():
            sensor_data_buffer.clear()
        for controller_data_buffer in self.controller_data_buffers.values():
            controller_data_buffer.clear()
        debug_print(self.name, "Pipe cleaned!", "INFO")

    def finish(self, episode_id=None):
        if self.start_event.is_set():
            self.start_event.clear()
            
            for sensor_data_buffer in self.sensor_data_buffers.values():
                datas = sensor_data_buffer.get()
                for data in datas:
                    d = [None, data]
                    self.collect(d)

                sensor_data_buffer.clear()

            for controller_data_buffer in self.controller_data_buffers.values():
                datas = controller_data_buffer.get()
                for data in datas:
                    d = [data, None]
                    self.collect(d)
                
                controller_data_buffer.clear()
        
        super().finish(episode_id=episode_id)
    
    def reset(self):
        for controller_data_buffer in self.controller_data_buffers.values():
            controller_data_buffer.clear()

        for sensor_data_buffer in self.sensor_data_buffers.values():
            sensor_data_buffer.clear()
        super().reset()
