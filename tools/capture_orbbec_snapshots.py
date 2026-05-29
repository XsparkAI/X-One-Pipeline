#!/usr/bin/env python3
"""Capture one color frame from each Orbbec camera and save to disk."""

import argparse
import os
import sys
from datetime import datetime

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from robot.sensor.Orbbec_sensor import OrbbecSensor, resolve_camera_color_settings
from robot.utils.base.load_file import load_yaml

CAMERA_ROLES = ("head", "left_wrist", "right_wrist")


def _frame_stats(frame_rgb):
    mean = frame_rgb.reshape(-1, 3).mean(axis=0)
    return float(mean[0]), float(mean[1]), float(mean[2])


def _annotate(frame_rgb, lines):
    bgr = frame_rgb[:, :, ::-1].copy()
    y = 28
    for line in lines:
        cv2.putText(bgr, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        y += 28
    return bgr


def capture_role(role, serial, color_settings, warmup_frames, output_dir):
    sensor = OrbbecSensor(f"cam_{role}")
    try:
        sensor.set_up(CAMERA_SERIAL=serial, is_depth=False, color_settings=color_settings)
        sensor.set_collect_info(["color"])

        frame = None
        for _ in range(warmup_frames):
            frame = sensor.get()["color"]

        r_mean, g_mean, b_mean = _frame_stats(frame)
        settings_text = (
            f"exp={color_settings['exposure']} gain={color_settings['gain']} "
            f"wb={color_settings['white_balance']}"
        )
        stats_text = f"mean_rgb=({r_mean:.1f}, {g_mean:.1f}, {b_mean:.1f})"

        raw_path = os.path.join(output_dir, f"{role}.jpg")
        annotated_path = os.path.join(output_dir, f"{role}_annotated.jpg")
        cv2.imwrite(raw_path, frame[:, :, ::-1])
        cv2.imwrite(
            annotated_path,
            _annotate(
                frame,
                [role, f"serial={serial}", settings_text, stats_text],
            ),
        )

        return {
            "role": role,
            "serial": serial,
            "settings": color_settings,
            "mean_rgb": (r_mean, g_mean, b_mean),
            "raw_path": raw_path,
            "annotated_path": annotated_path,
            "frame": frame,
        }
    finally:
        sensor.cleanup()


def build_grid(captures, output_dir):
    frames = [item["frame"] for item in captures]
    if not frames:
        return None

    target_h = min(frame.shape[0] for frame in frames)
    resized = []
    for item, frame in zip(captures, frames):
        scale = target_h / frame.shape[0]
        target_w = int(frame.shape[1] * scale)
        bgr = cv2.resize(frame[:, :, ::-1], (target_w, target_h))
        label = f"{item['role']} ({item['serial']})"
        cv2.putText(bgr, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
        resized.append(bgr)

    grid = cv2.hconcat(resized)
    grid_path = os.path.join(output_dir, "all_cameras.jpg")
    cv2.imwrite(grid_path, grid)
    return grid_path


def main():
    parser = argparse.ArgumentParser(description="Capture snapshots from all Orbbec cameras")
    parser.add_argument(
        "--cfg",
        default=os.path.join(ROOT, "config", "x-one-piperX-orbbec.yml"),
        help="Robot config yaml path",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory (default: ./data/camera_snapshots/<timestamp>)",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=5,
        help="Frames to discard before saving (default: 5)",
    )
    args = parser.parse_args()

    base_cfg = load_yaml(args.cfg)
    robot_config = base_cfg["robot"]
    serials = robot_config["CAMERA_SERIALS"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or os.path.join(ROOT, "data", "camera_snapshots", timestamp)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Config: {args.cfg}")
    print(f"Output: {output_dir}")
    print(f"Warmup frames: {args.warmup_frames}\n")

    captures = []
    for role in CAMERA_ROLES:
        serial = serials[role]
        settings = resolve_camera_color_settings(robot_config, role)
        print(f"Capturing {role} (serial={serial}) ...")
        try:
            result = capture_role(role, serial, settings, args.warmup_frames, output_dir)
            captures.append(result)
            r, g, b = result["mean_rgb"]
            print(
                f"  saved: {result['raw_path']}\n"
                f"  settings: exposure={settings['exposure']} gain={settings['gain']} "
                f"white_balance={settings['white_balance']}\n"
                f"  mean_rgb=({r:.1f}, {g:.1f}, {b:.1f})\n"
            )
        except Exception as exc:
            print(f"  FAILED: {exc}\n")

    if captures:
        grid_path = build_grid(captures, output_dir)
        if grid_path:
            print(f"Combined preview: {grid_path}")

    if len(captures) < len(CAMERA_ROLES):
        missing = [role for role in CAMERA_ROLES if role not in {item["role"] for item in captures}]
        print(f"Warning: missing cameras: {', '.join(missing)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
