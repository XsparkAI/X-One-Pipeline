import numpy as np

class Your_Policy:
    def __init__(self, usr_args):
        # Initialize your policy model here according to usr_args
        pass

    def update_obs(self, obs):
        # Update the observation cache or window here
        pass

    def get_action(self):
        # Compute and return the action(s) based on the current observation cache/window
        # model.infer(...) -> actions: np.array (chunk_size, action_size)
        actions = np.random.rand(10, 14)
        ret_actions = []
        for action in actions:
            ret_action = {
                "arm":{
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