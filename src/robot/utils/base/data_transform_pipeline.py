import sys
sys.path.append('./')

from robot.utils.base.data_handler import debug_print
import subprocess
import h5py
import numpy as np
import cv2
import os
import json

def image_rgb_encode_pipeline(collection, save_path, episode_id, mapping):
    def images_encoding(imgs):
        encode_data = []
        padded_data = []
        max_len = 0
        for i in range(len(imgs)):
            success, encoded_image = cv2.imencode(".jpg", imgs[i])
            jpeg_data = encoded_image.tobytes()
            encode_data.append(jpeg_data)
            max_len = max(max_len, len(jpeg_data))
        for i in range(len(imgs)):
            padded_data.append(encode_data[i].ljust(max_len, b"\0"))
        return encode_data, max_len
    
    hdf5_path = os.path.join(save_path, f"{episode_id}.hdf5")

    with h5py.File(hdf5_path, "w") as f:
        obs = f
        for name, items in mapping.items():
            group = obs.create_group(name)
            if name in collection.condition["image"]:
                for item in items:
                    data = collection.get_item(name, item)
                    if item == "color":
                        img_rgb_enc, img_rgb_len = images_encoding(data)
                        debug_print(f"image_rgb_encode_pipeline", f"success encode rgb data for {name}", "INFO")
                        group.create_dataset("color", data=img_rgb_enc, dtype=f"S{img_rgb_len}")
                    else:
                        group.create_dataset(item, data=data)
            else:
                for item in items:
                    data = collection.get_item(name, item)
                    group.create_dataset(item, data=data)
    
    debug_print("image_rgb_encode_pipeline", f"save data success at: {hdf5_path}!", "INFO")

def general_hdf5_rdt_format_pipeline(collection, save_path, episode_id, mapping):
    def images_encoding(imgs):
        encode_data = []
        padded_data = []
        max_len = 0
        for i in range(len(imgs)):
            success, encoded_image = cv2.imencode('.jpg', imgs[i])
            jpeg_data = encoded_image.tobytes()
            encode_data.append(jpeg_data)
            max_len = max(max_len, len(jpeg_data))
        # padding
        for i in range(len(imgs)):
            padded_data.append(encode_data[i].ljust(max_len, b'\0'))
        return encode_data, max_len

    hdf5_path = os.path.join(save_path, f"{episode_id}.hdf5")
    with h5py.File(hdf5_path, "w") as f:
        left_joint, left_gripper = collection.get_item("left_arm", "joint"), collection.get_item("left_arm", "gripper")
        right_joint, right_gripper = collection.get_item("right_arm", "joint"), collection.get_item("right_arm", "gripper")
        
        qpos = np.concatenate([left_joint, left_gripper, right_joint, right_gripper], axis=1)

        actions = []
        for i in range(len(qpos) - 1):
            actions.append(qpos[i+1])
        last_action = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        actions.append(last_action)

        cam_head = collection.get_item("cam_head", "color")
        cam_left_wrist = collection.get_item("cam_left_wrist", "color")
        cam_right_wrist = collection.get_item("cam_right_wrist", "color")

        head_enc, head_len = images_encoding(cam_head)
        left_enc, left_len = images_encoding(cam_left_wrist)
        right_enc, right_len = images_encoding(cam_right_wrist)

        f.create_dataset('action', data=np.array(actions), dtype="float32")
        observation = f.create_group("observations")
        observation.create_dataset('qpos', data=np.array(qpos), dtype="float32")
        images = observation.create_group("images")

        images.create_dataset('cam_high', data=head_enc, dtype=f'S{head_len}')
        images.create_dataset('cam_left_wrist', data=left_enc, dtype=f'S{left_len}')
        images.create_dataset('cam_right_wrist', data=right_enc, dtype=f'S{right_len}')
    
    debug_print("general_hdf5_rdt_format_pipeline", f"save data success at: {hdf5_path}!", "INFO")

def X_one_format_pipeline(collection, save_path, episode_id, mapping):
    output_path = os.path.join(save_path, f"episode{episode_id}")

    debug_print("X_one_format_pipeline", f"save to: {output_path}/ start!", "INFO")
    left_eef, left_joint, left_gripper, left_timestamp = collection.get_item("left_arm", "qpos"), collection.get_item("left_arm", "joint"), \
                                                        collection.get_item("left_arm", "gripper"), collection.get_item("left_arm", "timestamp")
    right_eef, right_joint, right_gripper, right_timestamp = collection.get_item("right_arm", "qpos"), collection.get_item("right_arm", "joint"),\
                                                        collection.get_item("right_arm", "gripper"), collection.get_item("right_arm", "timestamp")

    def decode(imgs):
        # print(type(imgs), len(imgs.shape))
        ret_imgs = []
        if isinstance(imgs, bytes) or (isinstance(imgs,np.ndarray) and len(imgs.shape) == 1):
            for img in imgs:
                jpeg_bytes = img.tobytes().rstrip(b"\0")
                nparr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                ret_imgs.append(cv2.imdecode(nparr, 1))
        else:
            ret_imgs = imgs
        return ret_imgs

    cam_head, cam_head_timestamp = decode(collection.get_item("cam_head", "color")), collection.get_item("cam_head", "timestamp")
    cam_left_wrist, cam_left_wrist_timestamp = decode(collection.get_item("cam_left_wrist", "color")), collection.get_item("cam_left_wrist", "timestamp")
    cam_right_wrist, cam_right_wrist_timestamp = decode(collection.get_item("cam_right_wrist", "color")), collection.get_item("cam_right_wrist", "timestamp")

    def save_video_from_frames(
        frames,
        save_path,
        filename,
        fps=30,
        is_rgb=True,
        crf=0,              # ⭐ 控制损失率，0=无损，10≈几乎无损
    ):
        """
        使用 FFmpeg 生成 near-lossless MP4（yuv444）
        
        frames: List[np.ndarray], shape (H, W, 3), uint8
        save_path: 输出目录
        filename: xxx.mp4
        fps: 帧率
        is_rgb: True 表示 frames 是 RGB（推荐）
        crf: H.264 CRF，0=无损，10~12=dataset 推荐
        """

        if len(frames) == 0:
            raise ValueError(f"No frames to save for {filename}")

        os.makedirs(save_path, exist_ok=True)
        video_path = os.path.join(save_path, filename)

        h, w, c = frames[0].shape
        assert c == 3, "Frames must be HxWx3"
        assert frames[0].dtype == np.uint8, "Frames must be uint8"

        # FFmpeg 命令
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24" if is_rgb else "bgr24",
            "-s", f"{w}x{h}",
            "-framerate", str(fps),   # ⭐ 输入帧率（比 -r 正确）
            "-i", "-",                # stdin
            "-an",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv444p",    # ⭐ 不丢色度
            "-crf", str(crf),
            video_path,
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        for frame in frames:
            if not is_rgb:
                # 如果是 BGR，转成 RGB 给 ffmpeg
                frame = frame[:, :, ::-1]
            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        ret = proc.wait()

        if ret != 0:
            raise RuntimeError("FFmpeg video encoding failed")

        return video_path
    
    save_video_from_frames(cam_head, output_path, "cam_head.mp4")
    save_video_from_frames(cam_left_wrist, output_path, "cam_left_wrist.mp4")
    save_video_from_frames(cam_right_wrist, output_path, "cam_right_wrist.mp4")

    hdf5_path = os.path.join(output_path, f"robotpose.hdf5")
    with h5py.File(hdf5_path, "w") as f:
        left_arm = f.create_group("left_arm")
        right_arm = f.create_group("right_arm")

        left_joint = left_arm.create_dataset("joint", data=left_joint)
        left_qpos = left_arm.create_dataset("qpos", data=left_eef)
        left_gripper = left_arm.create_dataset("gripper", data=left_gripper)

        right_joint = right_arm.create_dataset("joint", data=right_joint)
        right_qpos = right_arm.create_dataset("qpos", data=right_eef)
        right_gripper = right_arm.create_dataset("gripper", data=right_gripper)

    info = {
        "episode_id": episode_id,
        "timestamps": {
            "left_arm": {
                "timestamp": left_timestamp.tolist()
            },
            "right_arm": {
                "timestamp": right_timestamp.tolist()
            },
            "cam_head": {
                "timestamp": cam_head_timestamp.tolist()
            },
            "cam_left_wrist": {
                "timestamp": cam_left_wrist_timestamp.tolist()
            },
            "cam_right_wrist": {
                "timestamp": cam_right_wrist_timestamp.tolist()
            }
        }
    }

    info_path = os.path.join(output_path, "info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

    debug_print("X_one_format_pipeline", f"save data success at: {output_path} !", "INFO")


def diff_freq_pipeline(collection, save_path, episode_id, mapping):
    import os
    import cv2
    import h5py
    import numpy as np

    # =======================
    # 1. 读取机械臂数据
    # =======================
    left_eef = np.asarray(collection.get_item("left_arm", "qpos"))
    left_joint = np.asarray(collection.get_item("left_arm", "joint"))
    left_gripper = np.asarray(collection.get_item("left_arm", "gripper"))
    left_timestamp = np.asarray(collection.get_item("left_arm", "timestamp"))

    right_eef = np.asarray(collection.get_item("right_arm", "qpos"))
    right_joint = np.asarray(collection.get_item("right_arm", "joint"))
    right_gripper = np.asarray(collection.get_item("right_arm", "gripper"))
    right_timestamp = np.asarray(collection.get_item("right_arm", "timestamp"))

    def decode(imgs):
        """
        imgs:
          - list[bytes] / np.ndarray(dtype=object)
          - or np.ndarray(H,W,3)
        """
        if isinstance(imgs, (list, tuple)) or (
            isinstance(imgs, np.ndarray) and imgs.dtype == object
        ):
            ret = []
            for b in imgs:
                nparr = np.frombuffer(b, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                assert img is not None, "JPEG decode failed"
                ret.append(img)
            return np.asarray(ret)
        else:
            return np.asarray(imgs)

    cam_head_color = decode(collection.get_item("cam_head", "color"))
    cam_head_timestamp = np.asarray(collection.get_item("cam_head", "timestamp"))

    cam_left_wrist_color = decode(collection.get_item("cam_left_wrist", "color"))
    cam_left_wrist_timestamp = np.asarray(collection.get_item("cam_left_wrist", "timestamp"))

    cam_right_wrist_color = decode(collection.get_item("cam_right_wrist", "color"))
    cam_right_wrist_timestamp = np.asarray(collection.get_item("cam_right_wrist", "timestamp"))

    cam_len = len(cam_head_timestamp)

    left_indices = []
    right_indices = []

    left_ptr = 0
    right_ptr = 0
    left_max = len(left_timestamp) - 1
    right_max = len(right_timestamp) - 1

    for i in range(cam_len):
        avg_ts = int(
            (int(cam_head_timestamp[i]) +
             int(cam_left_wrist_timestamp[i]) +
             int(cam_right_wrist_timestamp[i])) / 3
        )

        # -------- left arm --------
        while left_ptr < left_max and left_timestamp[left_ptr + 1] < avg_ts:
            left_ptr += 1

        if left_ptr < left_max:
            if abs(left_timestamp[left_ptr + 1] - avg_ts) < abs(left_timestamp[left_ptr] - avg_ts):
                left_idx = left_ptr + 1
            else:
                left_idx = left_ptr
        else:
            left_idx = left_ptr

        left_indices.append(left_idx)

        # -------- right arm --------
        while right_ptr < right_max and right_timestamp[right_ptr + 1] < avg_ts:
            right_ptr += 1

        if right_ptr < right_max:
            if abs(right_timestamp[right_ptr + 1] - avg_ts) < abs(right_timestamp[right_ptr] - avg_ts):
                right_idx = right_ptr + 1
            else:
                right_idx = right_ptr
        else:
            right_idx = right_ptr

        right_indices.append(right_idx)

    left_indices = np.asarray(left_indices, dtype=np.int64)
    right_indices = np.asarray(right_indices, dtype=np.int64)

    left_joint = left_joint[left_indices]
    left_eef = left_eef[left_indices]
    left_gripper = left_gripper[left_indices]
    left_timestamp = left_timestamp[left_indices]

    right_joint = right_joint[right_indices]
    right_eef = right_eef[right_indices]
    right_gripper = right_gripper[right_indices]
    right_timestamp = right_timestamp[right_indices]

    # 移动判定
    tolerance = 0.00001
    indices = []
    prev_qpos = None

    for i in range(len(right_joint)):
        current_qpos = np.concatenate([
            left_joint[i].reshape(-1),
            left_gripper[i].reshape(-1),
            right_joint[i].reshape(-1),
            right_gripper[i].reshape(-1),
        ])

        if prev_qpos is None or np.any(np.abs(current_qpos - prev_qpos) > tolerance):
                indices.append(i)
                prev_qpos = current_qpos
    
    left_joint = left_joint[indices]
    left_eef = left_eef[indices]
    left_gripper = left_gripper[indices]
    left_timestamp = left_timestamp[indices]

    right_joint = right_joint[indices]
    right_eef = right_eef[indices]
    right_gripper = right_gripper[indices]
    right_timestamp = right_timestamp[indices]

    cam_head_color = cam_head_color[indices]
    cam_head_timestamp = cam_head_timestamp[indices]

    cam_left_wrist_color = cam_left_wrist_color[indices]
    cam_left_wrist_timestamp = cam_left_wrist_timestamp[indices]

    cam_right_wrist_color = cam_right_wrist_color[indices]
    cam_right_wrist_timestamp = cam_right_wrist_timestamp[indices]

    os.makedirs(save_path, exist_ok=True)
    hdf5_path = os.path.join(save_path, f"{episode_id}.hdf5")

    with h5py.File(hdf5_path, "w") as f:
        left_arm = f.create_group("left_arm")
        right_arm = f.create_group("right_arm")

        cam_head = f.create_group("cam_head")
        cam_left_wrist = f.create_group("cam_left_wrist")
        cam_right_wrist = f.create_group("cam_right_wrist")

        left_arm.create_dataset("joint", data=left_joint)
        left_arm.create_dataset("qpos", data=left_eef)
        left_arm.create_dataset("gripper", data=left_gripper)
        left_arm.create_dataset("timestamp", data=left_timestamp)

        right_arm.create_dataset("joint", data=right_joint)
        right_arm.create_dataset("qpos", data=right_eef)
        right_arm.create_dataset("gripper", data=right_gripper)
        right_arm.create_dataset("timestamp", data=right_timestamp)

        cam_head.create_dataset("color", data=cam_head_color)
        cam_head.create_dataset("timestamp", data=cam_head_timestamp)

        cam_left_wrist.create_dataset("color", data=cam_left_wrist_color)
        cam_left_wrist.create_dataset("timestamp", data=cam_left_wrist_timestamp)

        cam_right_wrist.create_dataset("color", data=cam_right_wrist_color)
        cam_right_wrist.create_dataset("timestamp", data=cam_right_wrist_timestamp)

    debug_print(
        "diff_freq_pipeline",
        f"save data success at: {hdf5_path}",
        "INFO"
    )