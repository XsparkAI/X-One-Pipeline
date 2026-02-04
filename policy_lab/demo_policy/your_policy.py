import numpy as np
from robot.utils.base.data_handler import debug_print, hdf5_groups_to_dict, dict_to_list

class Replay:
    def __init__(self, hdf5_path, chunk_size=10) -> None:
        debug_print("OfflineEval", f"Replay data: {hdf5_path}.", "INFO")
        self.ptr = 0
        self.episode = dict_to_list(hdf5_groups_to_dict(hdf5_path))
        self.chunk_size = chunk_size
    
    def infer(self):
        action_chunk = []
        for _ in range(self.chunk_size):
            data = self.episode[min(self.ptr, len(self.episode) - 1)]
            self.ptr += 1

            action = np.concatenate([
                np.array(data["left_arm"]["joint"]).reshape(-1),
                np.array(data["left_arm"]["gripper"]).reshape(-1),
                np.array(data["right_arm"]["joint"]).reshape(-1),
                np.array(data["right_arm"]["gripper"]).reshape(-1)
            ])
            print(action)

            action_chunk.append(action)
        
        return np.array(action_chunk)

class Your_Policy:
    def __init__(self, usr_args=None):
        # Initialize your policy model here
        self.usr_args = usr_args
        self.model = Replay(usr_args.get("data_path", "data/test_robot/test/0.hdf5"))
        
    def update_obs(self, obs):
        # 如果你后面要用历史窗口，可以存在这里
        self.last_obs = obs

    def get_action(self, obs=None):
        if obs is not None:
            self.update_obs(obs)
        
        actions = self.model.infer()
        # actions = np.random.rand(10, 14)

        ret_actions = []
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
                }
            }
            ret_actions.append(ret_action)

        return ret_actions

    def set_language(self, instruction):
        # Set the language instruction for the model here
        pass

    def reset(self):
        # Reset the observation cache or window here
        pass