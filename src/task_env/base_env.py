from robot.robot import get_robot

class BaseEnv:
    def __init__(self, base_cfg):
        self.episode_idx = None
        self.episode_step = 0
 
        self.robot = get_robot(robot_cfg=base_cfg['robot'])
    
    def set_up(self, teleop=False):
        self.robot.set_up(teleop=teleop)
    
    def set_episode_idx(self, idx):
        self.episode_idx = idx
    
    def take_action(self, action):
        self.robot.move(action)
    
    def get_obs(self):
        return self.robot.get_obs()