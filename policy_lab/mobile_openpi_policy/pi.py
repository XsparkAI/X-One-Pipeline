import numpy as np
import os
from robot.utils.base.data_handler import debug_print, dict_to_list, hdf5_groups_to_dict
import numpy as np
import cv2

from openpi.policies import policy_config as _policy_config
from openpi.training import config as _config

class PI_MOBILE:
    def __init__(self, deploy_cfg):
        train_config_name = deploy_cfg.get("train_config_name")

        print(f"Use config: {train_config_name}")
        config = _config.get_config(train_config_name)
        print("get config success!")
        self.policy = _policy_config.create_trained_policy(config, deploy_cfg['model_path'])
        print("loading model success!")

        self.observation_window = None
        self.instruction = None

    def set_language(self, instruction):
        self.instruction = instruction

    def update_obs(self, obs):
        state = np.concatenate([
            np.array(obs[0]["left_arm"]["joint"]).reshape(-1),
            np.array(obs[0]["left_arm"]["gripper"]).reshape(-1),
            np.array(obs[0]["right_arm"]["joint"]).reshape(-1),
            np.array(obs[0]["right_arm"]["gripper"]).reshape(-1),
            np.array(obs[0]["slamware"]["move_velocity"]).reshape(-1),
        ])

        def decode(img):
            jpeg_bytes = np.array(img).tobytes().rstrip(b"\0")
            nparr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            return cv2.imdecode(nparr, 1)

        img_front = decode(obs[1]["cam_head"]["color"])
        img_right = decode(obs[1]["cam_right_wrist"]["color"])
        img_left = decode(obs[1]["cam_left_wrist"]["color"])
        
        img_front = np.transpose(img_front, (2, 0, 1))
        img_right = np.transpose(img_right, (2, 0, 1))
        img_left = np.transpose(img_left, (2, 0, 1))

        self.observation_window = {
            "state": state,
            "images": {
                "cam_high": img_front,
                "cam_left_wrist": img_left,
                "cam_right_wrist": img_right,
            },
            "prompt": self.instruction,
        }
    
    def get_action(self, obs=None):
        if obs is not None:
            self.update_obs(obs)
        
        ret_actions = []

        actions = self.policy.infer(self.observation_window)["actions"]
        for action in actions:
            ret_action = {
                "arm": {
                    "left_arm": {
                        "joint": action[:6],
                        "gripper": action[6],
                    },
                    "right_arm": {
                        "joint": action[7:13],
                        "gripper": action[13],
                    }
                },
                "mobile": {
                    "slamware":{
                        "move_velocity": action[14:17],
                    }
                },
            }
            ret_actions.append(ret_action)

        return ret_actions

    def reset(self):
        # Reset the observation cache or window here
        self.observation_window = None
        self.instruction = None
        print("successfully reset observation_window and instruction")