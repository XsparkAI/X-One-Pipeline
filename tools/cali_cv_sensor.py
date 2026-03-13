import sys
sys.path.append("./")

import cv2
import numpy as np
import argparse
import os

from robot.sensor.Cv_sensor import CvSensor
from robot.utils.base.data_handler import is_enter_pressed

CHECKERBOARD = (11, 8)


def get_imgs(cv_sensor, img_num=10):
    frames = []

    print(f"[INFO] Press ENTER to capture image ({img_num} total)")
    while len(frames) < img_num:
        img_color = cv_sensor.get()["color"]
        cv2.imshow("img_color", img_color)
        key = cv2.waitKey(1)

        if is_enter_pressed():
            frames.append(img_color.copy())
            print(f"[INFO] Captured {len(frames)}/{img_num}")

    cv2.destroyAllWindows()
    return frames


def calibrate_and_save(imgs, save_path):
    objp = np.zeros((1, CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[0, :, :2] = np.mgrid[
        0:CHECKERBOARD[0], 0:CHECKERBOARD[1]
    ].T.reshape(-1, 2)

    objpoints = []
    imgpoints = []

    for img in imgs:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ret, corners = cv2.findChessboardCorners(
            gray,
            CHECKERBOARD,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK
        )

        if ret:
            corners = cv2.cornerSubPix(
                gray,
                corners,
                (3, 3),
                (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
            )
            objpoints.append(objp)
            imgpoints.append(corners)

    assert len(objpoints) > 0, "No valid chessboard detected!"

    image_size = gray.shape[::-1]

    K = np.zeros((3, 3))
    D = np.zeros((4, 1))
    rvecs, tvecs = [], []

    rms, _, _, _, _ = cv2.fisheye.calibrate(
        objpoints,
        imgpoints,
        image_size,
        K,
        D,
        rvecs,
        tvecs,
        flags=(
            cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC +
            cv2.fisheye.CALIB_CHECK_COND +
            cv2.fisheye.CALIB_FIX_SKEW
        ),
        criteria=(
            cv2.TERM_CRITERIA_EPS +
            cv2.TERM_CRITERIA_MAX_ITER,
            100,
            1e-6
        )
    )

    print("===== Calibration Result =====")
    print("RMS error:", rms)
    print("K:\n", K)
    print("D:\n", D)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    np.savez(
        save_path,
        K=K,
        D=D,
        image_size=image_size,
        checkerboard=CHECKERBOARD,
        rms=rms
    )

    print(f"[INFO] Calibration saved to {save_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam_name", type=str, required=True)
    parser.add_argument("--img_num", type=int, default=10)
    args = parser.parse_args()

    save_path = f"save/calibrate/{args.cam_name}.npz"

    cv_sensor = CvSensor(args.cam_name)
    cv_sensor.set_up(device_index=args.cam_name)
    cv_sensor.set_collect_info(["color"])
    frames = get_imgs(cv_sensor, args.img_num)
    calibrate_and_save(frames, save_path)

if __name__ == "__main__":
    main()