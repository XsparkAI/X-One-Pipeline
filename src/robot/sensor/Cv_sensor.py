import cv2
import numpy as np
import time
from robot.sensor.base_vision_sensor import BaseVisionSensor
from robot.utils.base.data_handler import debug_print

class CvSensor(BaseVisionSensor):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.cap = None
        self.is_depth = False

    def set_up(self, device_index='', is_depth=False, is_jepg=False, is_undistort=False):
        """
        初始化摄像头
        :param device_index: 摄像头索引号（0 为默认摄像头）
        :param is_depth: 是否为深度摄像头（True 时必须外部提供深度数据）
        """
        self.is_depth = is_depth
        self.is_jepg = is_jepg
        self.is_undistort = is_undistort

        if self.is_undistort:
            self.calib = np.load(f"save/calibrate/{device_index}.npz")
        
        tried = []
        try:
            t0 = time.monotonic()

            try:
                dev_path = f"/dev/video{device_index}"
                self.cap = cv2.VideoCapture(device_index)
                tried.append(("path", dev_path))
            except Exception:
                self.cap = None

            t_open = time.monotonic() - t0

            if not self.cap or not self.cap.isOpened():
                # Fourth attempt: scan available /dev/video* entries
                import glob
                devs = sorted(glob.glob(f'/dev/video{device_index}'))
                for d in devs:
                    try:
                        self.cap = cv2.VideoCapture(d)
                        tried.append(("scan_path", d))
                        if self.cap and self.cap.isOpened():
                            break
                    except Exception:
                        self.cap = None
                self.cap = cv2.VideoCapture(device_index)

            t_open = time.monotonic() - t0
            if not self.cap or not self.cap.isOpened():
                # Build informative error
                tried_str = ",".join([f"{k}:{v}" for k, v in tried])
                raise RuntimeError(f"Failed to open camera (attempts={tried_str}) (open took {t_open:.3f}s)")

            # 设置分辨率和帧率
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            print(f"Started camera: {self.name} (Index: {device_index}) open_time={t_open:.3f}s tried={tried}")
        except Exception as e:
            self.cleanup()
            raise RuntimeError(f"Failed to initialize camera: {str(e)}")

    def get_image(self):
        """
        获取图像数据，返回 dict
        可能包含：
        - color: RGB 图像
        - depth: 深度图（如果 is_depth=True）
        """
        image = {}
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError("Camera is not opened.")

        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Failed to get frame from camera.")

        if "color" in self.collect_info:
            # OpenCV 默认是 BGR，需要转成 RGB
            image["color"] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if self.is_undistort:
                image["color"] = self._undistort_fisheye(image["color"])

        if "depth" in self.collect_info:
            if not self.is_depth:
                debug_print(self.name, "should use set_up(is_depth=True) to enable collecting depth image", "ERROR")
                raise ValueError("Depth capture not enabled.")
            else:
                # 普通摄像头没有深度，需要用户自己对接深度数据，这里用全零代替
                depth_image = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.uint16)
                image["depth"] = depth_image

        return image.copy()

    def _undistort_fisheye(self, img, scale=0.8):
        K = self.calib["K"]
        D = self.calib["D"]

        h, w = img.shape[:2]

        # 1️⃣ 构造新的相机内参（缩小焦距 → 不裁剪视野）
        K_new = K.copy()
        K_new[0, 0] *= scale   # fx
        K_new[1, 1] *= scale   # fy
        # cx, cy 保持不变

        # 2️⃣ 生成去畸变映射
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            K, D,
            np.eye(3),
            K_new,
            (w, h),
            cv2.CV_16SC2
        )

        # 3️⃣ 重映射（允许黑边）
        undistorted = cv2.remap(
            img,
            map1, map2,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )

        return undistorted


    def cleanup(self):
        """释放摄像头资源"""
        try:
            if self.cap and self.cap.isOpened():
                self.cap.release()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    def __del__(self):
        self.cleanup()

if __name__ == "__main__":
    cam = CvSensor("test_cv")
    # cam.set_up(0, is_undistort=True)  # 默认摄像头
    cam.set_up(4, is_undistort=False, is_jepg=True)  # 默认摄像头
    cam.set_collect_info(["color"])  # 只采集彩色
    cam_list = []
    for i in range(10000000):
        # print(i)
        # data = cam.get()
        # time.sleep(0.1)
        # cam_list.append(data)
        print(cam.get_image()["color"].shape)
        cv2.imshow("img", cam.get_image()["color"])
        cv2.waitKey(1)
        # time.sleep(0.1)
