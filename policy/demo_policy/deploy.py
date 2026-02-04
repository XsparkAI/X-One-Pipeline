def get_model(usr_args):
    # import packages and module here
    from policy.demo_policy.your_policy import Your_Policy
    # Initialize and return your policy model here according to usr_args
    model = Your_Policy(usr_args)
    return model

def eval_one_episode(TASK_ENV, model):

    instruction = TASK_ENV.get_instruction()
    model.set_language(instruction)

    while not TASK_ENV.is_episode_end(): # Check whether the episode ends

        obs = TASK_ENV.get_obs() # Get Observation
        model.update_obs(obs)  # Update Observation, `update_obs` here can be modified
        actions = model.get_action() # Get Action according to observation chunk

        for action_idx, action in enumerate(actions):
            TASK_ENV.take_action(action)

            if action_idx != len(actions) - 1:
                model.update_obs(obs)