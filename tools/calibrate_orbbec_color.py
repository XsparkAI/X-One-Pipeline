#!/usr/bin/env python3
"""Live Orbbec color calibration: align wrist WB/exposure with head using fixed params."""

import argparse
import os
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from robot.sensor.Orbbec_sensor import OrbbecSensor, resolve_camera_color_settings
from robot.utils.base.load_file import load_yaml

CAMERA_ROLES = ("head", "left_wrist", "right_wrist")
STEP = {
    "exposure": 4,
    "gain": 1,
    "white_balance": 100,
}


def _overlay(frame_rgb, lines):
    bgr = frame_rgb[:, :, ::-1].copy()
    y = 24
    for line in lines:
        cv2.putText(bgr, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)
        y += 22
    return bgr


def _frame_stats(frame_rgb):
    mean = frame_rgb.reshape(-1, 3).mean(axis=0)
    return float(mean[0]), float(mean[1]), float(mean[2])


def _print_config_snippet(robot_config, settings_by_role):
    print("\n# Paste into config/x-one-piper-orbbec.yml under robot.CAMERA_COLOR:")
    head = settings_by_role["head"]
    print("  CAMERA_COLOR:")
    print(f"    auto_exposure: false")
    print(f"    exposure: {head['exposure']}")
    print(f"    gain: {head['gain']}")
    print(f"    auto_white_balance: false")
    print(f"    white_balance: {head['white_balance']}")
    print("    by_camera:")
    for role in ("left_wrist", "right_wrist"):
        wrist = settings_by_role[role]
        overrides = {}
        for key in ("exposure", "gain", "white_balance"):
            if wrist[key] != head[key]:
                overrides[key] = wrist[key]
        if overrides:
            print(f"      {role}:")
            for key, value in overrides.items():
                print(f"        {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description="Calibrate Orbbec camera color settings")
    parser.add_argument(
        "--cfg",
        default=os.path.join(ROOT, "config", "x-one-piper-orbbec.yml"),
        help="Robot config yaml path",
    )
    args = parser.parse_args()

    base_cfg = load_yaml(args.cfg)
    robot_config = base_cfg["robot"]
    serials = robot_config["CAMERA_SERIALS"]

    settings_by_role = {
        role: resolve_camera_color_settings(robot_config, role) for role in CAMERA_ROLES
    }
    sensors = {}
    for role in CAMERA_ROLES:
        sensor = OrbbecSensor(f"cam_{role}")
        sensor.set_up(
            CAMERA_SERIAL=serials[role],
            is_depth=False,
            color_settings=dict(settings_by_role[role]),
        )
        sensor.set_collect_info(["color"])
        sensors[role] = sensor

    selected = 0
    print("Controls:")
    print("  1/2/3      select head / left_wrist / right_wrist")
    print("  e/E        exposure -/+")
    print("  g/G        gain -/+")
    print("  w/W        white_balance -/+")
    print("  m          copy head white_balance to both wrists")
    print("  p          print YAML snippet")
    print("  q or ESC   quit")

    try:
        while True:
            role = CAMERA_ROLES[selected]
            settings = settings_by_role[role]
            frame = sensors[role].get()["color"]
            r_mean, g_mean, b_mean = _frame_stats(frame)
            head_stats = _frame_stats(sensors["head"].get()["color"]) if role != "head" else (r_mean, g_mean, b_mean)

            lines = [
                f"selected={role} serial={serials[role]}",
                f"exposure={settings['exposure']} gain={settings['gain']} wb={settings['white_balance']}",
                f"mean_rgb=({r_mean:.1f}, {g_mean:.1f}, {b_mean:.1f})",
            ]
            if role != "head":
                lines.append(
                    f"head_mean_rgb=({head_stats[0]:.1f}, {head_stats[1]:.1f}, {head_stats[2]:.1f})"
                )
            cv2.imshow("orbbec_color_calibrate", _overlay(frame, lines))

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key in (ord("1"), ord("2"), ord("3")):
                selected = int(chr(key)) - 1
                continue
            if key == ord("p"):
                _print_config_snippet(robot_config, settings_by_role)
                continue
            if key == ord("m"):
                head_wb = settings_by_role["head"]["white_balance"]
                for wrist_role in ("left_wrist", "right_wrist"):
                    settings_by_role[wrist_role]["white_balance"] = head_wb
                    settings_by_role[wrist_role]["auto_white_balance"] = False
                    sensors[wrist_role].cleanup()
                    sensors[wrist_role].set_up(
                        CAMERA_SERIAL=serials[wrist_role],
                        is_depth=False,
                        color_settings=dict(settings_by_role[wrist_role]),
                    )
                    sensors[wrist_role].set_collect_info(["color"])
                print(f"Synced wrist white_balance to head value {head_wb}")
                continue

            delta = None
            field = None
            if key == ord("e"):
                delta, field = -STEP["exposure"], "exposure"
            elif key == ord("E"):
                delta, field = STEP["exposure"], "exposure"
            elif key == ord("g"):
                delta, field = -STEP["gain"], "gain"
            elif key == ord("G"):
                delta, field = STEP["gain"], "gain"
            elif key == ord("w"):
                delta, field = -STEP["white_balance"], "white_balance"
            elif key == ord("W"):
                delta, field = STEP["white_balance"], "white_balance"

            if delta is None:
                continue

            settings[field] = max(0, int(settings[field]) + delta)
            settings["auto_exposure"] = False
            settings["auto_white_balance"] = False
            sensors[role].cleanup()
            sensors[role].set_up(
                CAMERA_SERIAL=serials[role],
                is_depth=False,
                color_settings=dict(settings),
            )
            sensors[role].set_collect_info(["color"])
            print(f"{role}: {field}={settings[field]}")
    finally:
        for sensor in sensors.values():
            sensor.cleanup()
        cv2.destroyAllWindows()
        _print_config_snippet(robot_config, settings_by_role)


if __name__ == "__main__":
    main()
