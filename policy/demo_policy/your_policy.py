class Your_Policy:
    def __init__(self, usr_args):
        # Initialize your policy model here according to usr_args
        pass

    def update_obs(self, obs):
        # Update the observation cache or window here
        pass

    def get_action(self):
        # Compute and return the action(s) based on the current observation cache/window
        actions = []
        # ...
        return actions
    
    def set_language(self, instruction):
        # Set the language instruction for the model here
        pass

    def reset(self):
        # Reset the observation cache or window here
        pass