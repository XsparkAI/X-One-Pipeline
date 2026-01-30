import os
import fcntl
import mmap
import select
import numpy as np
import v4l2
import time
import cv2

from robot.sensor.vision_sensor import VisionSensor
from robot.utils.base.data_handler import debug_print

class V4l2Sensor(VisionSensor):
    """
    V4L2 摄像头采集（MJPEG）
    支持:
    - timestamp 对齐 host monotonic clock
    - JPEG 编码输出
    - 可选鱼眼畸变校正（黑边保留）
    """
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.fd = None
        self.buffers = []
        self.width = 640
        self.height = 480
        self.is_depth = False
        self.is_jepg = False
        self.is_undistort = False
        self.base_cam_ns = None

    def set_up(self, device: str, is_depth=False, is_jepg=False, is_undistort=False):
        self.is_depth = is_depth
        self.is_jepg = is_jepg
        self.is_undistort = is_undistort

        if self.is_undistort:
            self.calib = np.load(f"save/calibrate/{os.path.basename(device)}.npz")

        # 打开设备
        if self.fd is not None:
            self.cleanup()
        
        self.fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)

        # 设置格式
        fmt = v4l2.v4l2_format()
        fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        fmt.fmt.pix.width = self.width
        fmt.fmt.pix.height = self.height
        fmt.fmt.pix.pixelformat = v4l2.V4L2_PIX_FMT_MJPEG
        fmt.fmt.pix.field = v4l2.V4L2_FIELD_NONE
        fcntl.ioctl(self.fd, v4l2.VIDIOC_S_FMT, fmt)

        # 请求 buffer
        req = v4l2.v4l2_requestbuffers()
        req.count = 4
        req.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = v4l2.V4L2_MEMORY_MMAP
        fcntl.ioctl(self.fd, v4l2.VIDIOC_REQBUFS, req)

        # mmap buffer
        self.buffers = []
        for i in range(req.count):
            buf = v4l2.v4l2_buffer()
            buf.type = req.type
            buf.memory = v4l2.V4L2_MEMORY_MMAP
            buf.index = i
            fcntl.ioctl(self.fd, v4l2.VIDIOC_QUERYBUF, buf)

            mm = mmap.mmap(
                self.fd, buf.length,
                mmap.PROT_READ | mmap.PROT_WRITE,
                mmap.MAP_SHARED,
                offset=buf.m.offset
            )
            self.buffers.append(mm)

            # 队列入列
            fcntl.ioctl(self.fd, v4l2.VIDIOC_QBUF, buf)

        # 开始采集
        buf_type = v4l2.v4l2_buf_type(v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
        fcntl.ioctl(self.fd, v4l2.VIDIOC_STREAMON, buf_type)

    def get_image(self):
        """
        获取一帧图像，返回 dict:
        {
            "color": np.ndarray (RGB)
            "timestamp": int (ns, monotonic host-aligned)
        }
        """
        self.latest_image = None
        # 等待 frame 可读
        r, _, _ = select.select([self.fd], [], [], 2.0)
        if not r:
            return None
        
        buf = v4l2.v4l2_buffer()
        buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        buf.memory = v4l2.V4L2_MEMORY_MMAP
        fcntl.ioctl(self.fd, v4l2.VIDIOC_DQBUF, buf)

        cam_ns = int(buf.timestamp.secs * 1e9 + buf.timestamp.usecs * 1e3)

        # 取 buffer 数据
        data = self.buffers[buf.index][:buf.bytesused]

        # 再次入队
        fcntl.ioctl(self.fd, v4l2.VIDIOC_QBUF, buf)

        # 构建 image dict
        image = {}
        if "color" in self.collect_info:
            img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            img = img[:, :, ::-1]  # BGR -> RGB
            if self.is_undistort:
                img = self._undistort_fisheye(img)
            
            image["color"] = img

        if "depth" in self.collect_info:
            if not self.is_depth:
                debug_print(self.name, "should use set_up(is_depth=True) to enable collecting depth image", "ERROR")
                raise ValueError("Depth capture not enabled.")

        image["timestamp"] = cam_ns

        return image

    def _undistort_fisheye(self, img, scale=0.8):
        K = self.calib["K"]
        D = self.calib["D"]
        h, w = img.shape[:2]

        K_new = K.copy()
        K_new[0, 0] *= scale
        K_new[1, 1] *= scale

        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            K, D, np.eye(3), K_new, (w, h), cv2.CV_16SC2
        )
        undistorted = cv2.remap(img, map1, map2, interpolation=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return undistorted

    def cleanup(self):
        if self.fd is None:
            return

        # 1️⃣ 停止 stream
        try:
            buf_type = v4l2.v4l2_buf_type(v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
            fcntl.ioctl(self.fd, v4l2.VIDIOC_STREAMOFF, buf_type)
        except Exception as e:
            print(f"[{self.name}] STREAMOFF failed: {e}")

        # 2️⃣ unmap buffers（⚠️ 必须）
        for mm in self.buffers:
            try:
                mm.close()
            except Exception as e:
                print(f"[{self.name}] mmap close failed: {e}")
        self.buffers.clear()

        # 3️⃣ 关闭 fd
        try:
            os.close(self.fd)
        except Exception as e:
            print(f"[{self.name}] fd close failed: {e}")

        self.fd = None

if __name__ == "__main__":
    cam = V4l2Sensor("test_v4l2")
    cam.set_up("/dev/video0", is_undistort=False, is_jepg=False)
    cam.set_collect_info(["color"])

    for i in range(10):
        st = time.monotonic_ns()
        frame = cam.get_image()["color"][:,:,::-1]
        cv2.imshow("111", frame)
        cv2.waitKey(100)
    
    cam.cleanup()
    cam.set_up("/dev/video0", is_undistort=False, is_jepg=False)
    print("cleanup success!!!")
    for i in range(10000):
        st = time.monotonic_ns()
        frame = cam.get_image()["color"][:,:,::-1]
        cv2.imshow("111", frame)
        cv2.waitKey(1)
        # ts = frame["timestamp"]
        # en = time.monotonic_ns()
        # delta_ms = (time.monotonic_ns() - ts) / 1e6
        # print(f"st-get: {(ts -st)/1e6}, st-en: {(en-st)/1e6}, full: {(en - ts)/1e6}")
        # print(f"frame_ts: {ts}, delta_ms: {delta_ms:.2f}, img shape: {frame['color'].shape}")
