import numpy as np

class Your_Policy:
    def __init__(self, usr_args=None):
        # Initialize your policy model here
        self.usr_args = usr_args

    def update_obs(self, obs):
        # 如果你后面要用历史窗口，可以存在这里
        self.last_obs = obs

    def get_action(self, obs=None):
        if obs is not None:
            self.update_obs(obs)
        
        # actions = model.infer()
        actions = np.random.rand(10, 14)

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