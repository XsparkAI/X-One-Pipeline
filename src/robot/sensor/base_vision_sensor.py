from robot.sensor.sensor import Sensor
import numpy as np
from robot.utils.base.data_handler import debug_print

class BaseVisionSensor(Sensor):
    def __init__(self, TEST=False):
        super().__init__()
        self.name = "vision_sensor"
        self.type = "vision_sensor"
        self.collect_info = None
        self.TEST = TEST

    def get_information(self):
        image_info = {}
        try:
            image = self.get_image()
        except Exception as e:
            debug_print(self.name, f"Pipe break: {e}", "ERROR")
            image = {}
            image["color"] = None
            image["depth"] = None
        
        if "color" in self.collect_info:
            if getattr(self, "is_jpeg", False):
                import cv2
                img_raw = image["color"]
                if img_raw is not None:
                    if isinstance(img_raw, (bytes, bytearray)):
                        image["color"] = bytes(img_raw)
                    else:
                        success, encoded_image = cv2.imencode('.jpg', img_raw)
                        if success:
                            image["color"] = encoded_image.tobytes()
                        else:
                            image["color"] = None
                    if self.TEST and image["color"] is not None and not isinstance(img_raw, (bytes, bytearray)):
                        from robot.utils.base.data_handler import jpeg_test

                        result = jpeg_test(img_raw, image["color"])
                        print(f"{self.name} PSNR:", result["PSNR"])
                        print(f"{self.name} MSE:", result["MSE"])
                        print(f"{self.name} SSIM:", result["SSIM"])

            image_info["color"] = image.get("color")
        if "depth" in self.collect_info:
            image_info["depth"] = image["depth"]
        if "point_cloud" in self.collect_info:
            image_info["point_cloud"] = image["point_cloud"]
        
        if "timestamp" in image.keys():
            image_info["timestamp"] = image["timestamp"]
        
        return image_info