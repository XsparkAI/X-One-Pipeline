import importlib.util
from pathlib import Path

import cv2
import numpy as np

from robot.sensor.base_vision_sensor import BaseVisionSensor
from robot.utils.base.data_handler import debug_print


def find_device_by_serial(devices, serial):
    """Find device index by serial number."""
    for device in devices:
        if device["serial"] == serial:
            return device["index"]
    return None

class OrbbecSensor(BaseVisionSensor):
    """Simple Orbbec wrapper for a single head color + depth camera."""

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.is_depth = False
        self.is_jpeg = False
        self.depth_normalize = False
        self.context = None
        self.device = None
        self.pipeline = None
        self.sdk = None
        self.camera_serial = None
        self.color_width = 640
        self.color_height = 480
        self.color_fps = 30
        self.depth_width = 640
        self.depth_height = 480
        self.depth_fps = 30

    def _load_sdk(self):
        try:
            import pyorbbecsdk
            from pyorbbecsdk import (
                Config,
                Context,
                OBError,
                OBFormat,
                OBFrameAggregateOutputMode,
                OBSensorType,
                Pipeline,
            )

            sdk_module_path = Path(pyorbbecsdk.__file__).resolve()
            example_dirs = (
                sdk_module_path.parent / "pyorbbecsdk" / "examples",
                sdk_module_path.parent / "examples",
            )

            utils_module = None
            for examples_dir in example_dirs:
                utils_path = examples_dir / "utils.py"
                if not utils_path.exists():
                    continue
                spec = importlib.util.spec_from_file_location("pyorbbecsdk_examples_utils", utils_path)
                if spec is None or spec.loader is None:
                    continue
                utils_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(utils_module)
                break

            if utils_module is None or not hasattr(utils_module, "frame_to_bgr_image"):
                raise ImportError("Cannot find pyorbbecsdk examples/utils.py")

            self.sdk = {
                "Config": Config,
                "Context": Context,
                "Pipeline": Pipeline,
                "OBError": OBError,
                "OBFormat": OBFormat,
                "OBFrameAggregateOutputMode": OBFrameAggregateOutputMode,
                "OBSensorType": OBSensorType,
                "frame_to_bgr_image": utils_module.frame_to_bgr_image,
            }
        except ImportError as exc:
            raise RuntimeError(
                "Failed to import pyorbbecsdk. Please install pyorbbecsdk first."
            ) from exc

    def _iter_video_profiles(self, profile_list):
        get_count = getattr(profile_list, "get_count", None)
        get_profile_by_index = getattr(profile_list, "get_stream_profile_by_index", None)
        if not callable(get_count) or not callable(get_profile_by_index):
            return

        for index in range(get_count()):
            try:
                profile = get_profile_by_index(index)
            except Exception:
                continue
            as_video_stream_profile = getattr(profile, "as_video_stream_profile", None)
            if callable(as_video_stream_profile):
                try:
                    profile = as_video_stream_profile()
                except Exception:
                    continue
            yield profile

    def _get_video_profile(self, profile_list, width, height, preferred_formats, fps):
        profiles = list(self._iter_video_profiles(profile_list))
        format_priority = {frame_format: index for index, frame_format in enumerate(preferred_formats)}

        exact_matches = [
            profile
            for profile in profiles
            if profile.get_width() == width
            and profile.get_height() == height
            and profile.get_fps() == fps
            and profile.get_format() in format_priority
        ]
        if exact_matches:
            exact_matches.sort(key=lambda profile: format_priority[profile.get_format()])
            return exact_matches[0]

        get_profile = getattr(profile_list, "get_video_stream_profile", None)
        if callable(get_profile):
            for frame_format in preferred_formats:
                try:
                    return get_profile(width, height, frame_format, fps)
                except Exception:
                    continue

            # The application guide states width/height of 0 act as wildcards.
            for frame_format in preferred_formats:
                try:
                    return get_profile(0, 0, frame_format, fps)
                except Exception:
                    continue

        raise RuntimeError(
            f"Failed to find an Orbbec stream profile for {width}x{height}@{fps}"
        )

    def _profile_summary(self, profile):
        return (
            f"{profile.get_width()}x{profile.get_height()}@{profile.get_fps()} "
            f"{getattr(profile.get_format(), 'name', profile.get_format())}"
        )

    def _decode_color(self, color_frame):
        color_bgr = self.sdk["frame_to_bgr_image"](color_frame)
        if color_bgr is None:
            raise RuntimeError("Failed to decode Orbbec color frame")

        # Keep the same convention as RealsenseSensor: return RGB to upper layers.
        return color_bgr[:, :, ::-1].copy()

    def _decode_depth(self, depth_frame):
        depth = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
        depth = depth.reshape(depth_frame.get_height(), depth_frame.get_width())

        scale = getattr(depth_frame, "get_depth_scale", lambda: 1)()
        if scale not in (None, 0, 1):
            depth = (depth.astype(np.float32) * scale).astype(np.uint16)

        return depth.copy()

    def _open_failure_hint(self, exc):
        message = str(exc)
        if "openUsbDevice failed" in message:
            return (
                f"{message}. The camera is visible to the SDK but cannot be opened. "
                "Please check USB permissions / udev rules, then replug the device."
            )
        return message

    def _query_devices(self):
        self.context = self.sdk["Context"]()
        device_list = self.context.query_devices()

        get_count = getattr(device_list, "get_count", None)
        if not callable(get_count):
            raise RuntimeError("Failed to query Orbbec devices")

        if get_count() == 0:
            raise RuntimeError("No Orbbec devices found")

        return device_list

    def _resolve_device(self, camera_serial=None):
        self.camera_serial = camera_serial.strip() if isinstance(camera_serial, str) else None
        device_list = self._query_devices()

        if self.camera_serial is None:
            return None

        get_device_by_serial_number = getattr(device_list, "get_device_by_serial_number", None)
        if callable(get_device_by_serial_number):
            try:
                selected_device = get_device_by_serial_number(self.camera_serial)
                if selected_device is not None:
                    return selected_device
            except Exception:
                pass

        devices = []
        get_count = device_list.get_count
        for index in range(get_count()):
            try:
                devices.append(
                    {
                        "index": index,
                        "name": device_list.get_device_name_by_index(index),
                        "serial": device_list.get_device_serial_number_by_index(index),
                    }
                )
            except Exception:
                continue

        device_idx = find_device_by_serial(devices, self.camera_serial)
        get_device_by_index = getattr(device_list, "get_device_by_index", None)
        if device_idx is not None and callable(get_device_by_index):
            return get_device_by_index(device_idx)

        available = ", ".join(
            f"{item['name']}({item['serial']})" for item in devices if item.get("serial")
        ) or "unknown"
        raise RuntimeError(
            f"Could not find Orbbec camera with serial number {self.camera_serial}. "
            f"Available devices: {available}"
        )

    def set_up(
        self,
        CAMERA_SERIAL=None,
        is_depth=False,
        is_jpeg=False,
        depth_normalize=False,
    ):
        self.is_depth = is_depth
        self.is_jpeg = is_jpeg
        self.depth_normalize = depth_normalize

        self._load_sdk()
        self.cleanup()

        try:
            self.device = self._resolve_device(camera_serial=CAMERA_SERIAL)
            self.pipeline = self.sdk["Pipeline"](self.device) if self.device is not None else self.sdk["Pipeline"]()
            config = self.sdk["Config"]()

            color_profiles = self.pipeline.get_stream_profile_list(self.sdk["OBSensorType"].COLOR_SENSOR)
            color_profile = self._get_video_profile(
                color_profiles,
                self.color_width,
                self.color_height,
                (
                    self.sdk["OBFormat"].MJPG,
                    self.sdk["OBFormat"].RGB,
                    self.sdk["OBFormat"].YUYV,
                    self.sdk["OBFormat"].UYVY,
                ),
                self.color_fps,
            )
            config.enable_stream(color_profile)

            depth_profile = None
            if self.is_depth:
                depth_profiles = self.pipeline.get_stream_profile_list(self.sdk["OBSensorType"].DEPTH_SENSOR)
                depth_profile = self._get_video_profile(
                    depth_profiles,
                    self.depth_width,
                    self.depth_height,
                    (
                        self.sdk["OBFormat"].Y16,
                        self.sdk["OBFormat"].Z16,
                        self.sdk["OBFormat"].RW16,
                    ),
                    self.depth_fps,
                )
                config.enable_stream(depth_profile)
                config.set_frame_aggregate_output_mode(
                    self.sdk["OBFrameAggregateOutputMode"].FULL_FRAME_REQUIRE
                )

            self.pipeline.start(config)
            serial_info = self.camera_serial or "auto"
            debug_print(
                self.name,
                (
                    f"Started Orbbec stream: serial={serial_info} color={self._profile_summary(color_profile)} "
                    f"depth={self._profile_summary(depth_profile) if depth_profile is not None else 'off'}"
                ),
                "INFO",
            )
        except self.sdk["OBError"] as exc:
            self.cleanup()
            raise RuntimeError(self._open_failure_hint(exc)) from exc
        except Exception:
            self.cleanup()
            raise

    def get_image(self):
        if self.pipeline is None:
            raise RuntimeError("Orbbec camera is not initialized")

        image = {}
        frames = self.pipeline.wait_for_frames(1000)
        if frames is None:
            raise RuntimeError("Timed out waiting for Orbbec frames")

        color_frame = frames.get_color_frame()
        if color_frame is None:
            raise RuntimeError("Failed to get color frame")

        if "color" in self.collect_info:
            image["color"] = self._decode_color(color_frame)

        if "depth" in self.collect_info:
            if not self.is_depth:
                debug_print(self.name, "should use set_up(is_depth=True) to enable collecting depth image", "ERROR")
                raise ValueError("Depth capture not enabled. Use set_up(is_depth=True).")
            depth_frame = frames.get_depth_frame()
            if depth_frame is None:
                raise RuntimeError("Failed to get depth frame")
            
            depth = self._decode_depth(depth_frame)
            if self.depth_normalize:
                # 处理频闪：大于3m设为0
                depth[depth > 3000] = 0
                # 归一化到0-4m (4000mm)
                depth = np.clip(depth.astype(np.float32), 0, 4000) / 4000.0
                
            image["depth"] = depth

        return image

    def cleanup(self):
        if self.pipeline is None:
            self.device = None
            self.context = None
            return
        try:
            self.pipeline.stop()
        except Exception:
            pass
        self.pipeline = None
        self.device = None
        self.context = None

    def __del__(self):
        self.cleanup()

def visualize_depth(depth):
    if depth is None:
        return None

    depth = depth.astype(np.float32)
    
    # 判定是否已经归一化 (0-1)
    if np.max(depth) <= 1.0:
        # 如果已经归一化，认为它反映的是 0-4m 的比例
        depth_vis = (depth * 255).astype(np.uint8)
        valid = depth > 0
    else:
        # 否则使用 0-4m 固定范围归一化处理原始深度 (mm)
        # 过滤大于3m的数据处理频闪
        depth[depth > 3000] = 0
        valid = depth > 0
        depth_vis = np.zeros_like(depth, dtype=np.uint8)
        
        min_val = 0
        max_val = 4000
        if max_val > min_val:
            depth_norm = (depth - min_val) / (max_val - min_val)
            depth_vis[valid] = (depth_norm[valid] * 255).astype(np.uint8)

    depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
    depth_color[~valid] = 0
    return depth_color


if __name__ == "__main__":
    vis = OrbbecSensor("test")
    vis.set_up(CAMERA_SERIAL=None, is_depth=True)
    vis.set_collect_info(["color", "depth"])

    while True:
        data = vis.get()

        color_bgr = data["color"] # [:, :, ::-1]
        depth_bgr = visualize_depth(data.get("depth"))

        cv2.imshow("color", color_bgr)
        if depth_bgr is not None:
            cv2.imshow("depth", depth_bgr)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord("q"):
            break

    cv2.destroyAllWindows()
