import sys
sys.path.append('./')

import os
import importlib
import argparse
import numpy as np
import time
import yaml
import json

from robot.utils.base.data_handler import debug_print
from robot.data.collect_any import CollectAny
conditio
def get_class(import_name, class_name):
    try:n
        class_module = importlib.import_module(import_name)
        debug_print("function", f"Module loaded: {class_module}", "DEBUG")
    except ModuleNotFoundError as e:
        raise SystemExit(f"ModuleNotFoundError: {e}")

    try:
        return_class = getattr(class_module, class_name)
        debug_print("function", f"Class found: {return_class}", "DEBUG")

    except AttributeError as e:
        raise SystemExit(f"AttributeError: {e}")
    except Exception as e:
        raise SystemExit(f"Unexpected error instantiating model: {e}")
    return return_class

import time


class Deploy:
    def __init__(
        self,
        robot,
        policy,
        input_transform,
        output_transform,
        **kwargs,
    ):
        """
        robot: Robot 实例，必须有 get() / move(action)
        policy: policy 实例，必须有 update_obs() / get_action()
        input_transform: raw_obs -> policy_obs
        output_transform: policy_action -> robot_action
        fps: 控制频率
        """
        self.robot = robot
        self.policy = policy
        self.input_transform = input_transform
        self.output_transform = output_transform

        self.fps = getattr(kwargs["deploy"], "fps", 30)
        self.epoch = getattr(kwargs["deploy"], "epoch", 10)
        self.max_step = getattr(kwargs["deploy"], "max_step", 10000)
        self.save_video = getattr(kwargs["deploy"], "save_video", None)
        self.record = getattr(kwargs["deploy"], "record", False)
        self.info_path = os.path.join("./save/", self.robot.name, self.policy.task_name)

    def eval_once(self, eval_id):
        step = 0
        if self.save_video:
            first_frame = self.robot.get()[1][self.save_video]["color"]
            height, width, channels = first_frame.shape
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # 或 'XVID'
            video_dir = os.path.join(self.info_path, "/videos/", f"/{eval_id}/")
            os.makedirs(video_dir, exist_ok=True)
            self.writer = cv2.VideoWriter(os.path.join(video_dir, f"{video_cam_name}.mp4"), fourcc, fps, (width, height))
            debug_print("", f"Video saving enabled: {video_path}, fps={fps}, size=({width},{height})", "INFO")
        
        if self.record_frame:
            self.collection = CollectAny(condition=)


    def play_once(self):
        # 1. 获取机器人观测
        raw_obs = self.robot.get()

        # 2. 观测变换
        policy_obs = self.input_transform(raw_obs)

        # 3. 更新 policy 观测
        self.policy.update_obs(policy_obs)

        # 4. 获取动作（可能是 action sequence）
        actions = self.policy.get_action()

        # 5. 执行动作序列
        for action in actions:
            robot_action = self.output_transform(action)
            self.robot.move(robot_action)
            time.sleep(1.0 / self.fps)


    def record(self, data):
        if self.save_video:


def init(yml_path):
    if os.path.exists(yml_path):
        with open(yml_path, "r", encoding="utf-8") as f:
            yml_args = yaml.safe_load(f)
    if yml_args is None:
        raise ValueError(f"Invalid yml file: {yml_path}")

    robot_class = get_class(yml_args["robot"]["class"]["class_path"], yml_args["robot"]["class"]["class_name"])
    robot = robot_class(**yml_args["robot"]["init"]["args"])
    robot.set_up(**yml_args["robot"]["set_up"]["args"])

    policy_class = get_class(yml_args["policy"]["class"]["class_path"], yml_args["policy"]["class"]["class_name"])
    policy = policy_class(**yml_args["policy"]["init"]["args"])

    innput_transform = get_class(yml_args["input"]["func"]["func_path"], yml_args["policy"]["func"]["func_name"])
    output_transform = get_class(yml_args["output"]["func"]["func_path"], yml_args["output"]["func"]["func_name"])

    deploy = Deploy(robot, policy, input_transform, output_transform, yml_args)

