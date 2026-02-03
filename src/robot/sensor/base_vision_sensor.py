from robot.sensor.sensor import Sensor
import numpy as np
from robot.utils.base.data_handler import debug_print

class BaseVisionSensor(Sensor):
    def __init__(self, TEST=False):
        super().__init__()
        self.name = "vision_sensor"
        self.type = "vision_sensor"
        self.collect_info = None
        self.encode_rgb = False
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
            if getattr(self, "is_jepg", False):
                import cv2
                img_raw = image["color"]
                if img_raw is not None:
                    success, encoded_image = cv2.imencode('.jpg', image["color"]) # , [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                    jpeg_data = encoded_image.tobytes()
                    image["color"] = jpeg_data
                    if self.TEST:
                        jpeg_bytes = jpeg_data.rstrip(b"\0")
                        nparr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                        img_dec = cv2.imdecode(nparr, 1)

                        def mse(img1, img2):
                            return np.mean((img1.astype(np.float32) - img2.astype(np.float32)) ** 2)

                        print(f"{self.name} PSNR:", cv2.PSNR(img_raw, img_dec))
                        print(f"{self.name} MSE:", mse(img_raw, img_dec))
                        print(f"{self.name} SSIM:", ssim(img_raw, img_dec,channel_axis=-1,data_range=255))

            image_info["color"] = image["color"]
        if "depth" in self.collect_info:
            image_info["depth"] = image["depth"]
        if "point_cloud" in self.collect_info:
            image_info["point_cloud"] = image["point_cloud"]
        
        if "timestamp" in image.keys():
            image_info["timestamp"] = image["timestamp"]
        
        return image_info