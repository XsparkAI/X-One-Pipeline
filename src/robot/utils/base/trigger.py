import serial
import struct
import threading
import time
import logging

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TriggerSimple")

class TriggerData:
    def __init__(self):
        # 左手柄数据: [X轴, Y轴, 按键位掩码, 板机深度]
        self.left = [0, 0, 0, 0]
        # 右手柄数据: [X轴, Y轴, 按键位掩码, 板机深度]
        self.right = [0, 0, 0, 0]
        self.timestamp = 0

    def __str__(self):
        return (f"Left:  X={self.left[0]:6d}, Y={self.left[1]:6d}, Buttons={self.left[2]:5d}, Trigger={self.left[3]:6d}\n"
                f"Right: X={self.right[0]:6d}, Y={self.right[1]:6d}, Buttons={self.right[2]:5d}, Trigger={self.right[3]:6d}")

class TriggerReader:
    def __init__(self, port="/dev/ttyACM14", baudrate=2000000):
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial = None
        self.data = TriggerData()
        self.lock = threading.Lock()
        self.thread = None

        # 帧协议常量
        self.HEADER = 0xAA
        self.TAIL = 0x55
        self.FRAME_MIN_LEN = 51 # 最小帧长 (48B payload + 3B meta)

    def start(self):
        """启动读取线程"""
        if self.running:
            return
        
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            logger.info(f"TriggerReader started on {self.port}")
        except Exception as e:
            logger.error(f"Failed to start TriggerReader: {e}")
            raise

    def stop(self):
        """停止读取"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.serial:
            self.serial.close()
        logger.info("TriggerReader stopped")

    def get_data(self):
        """获取最新数据"""
        with self.lock:
            return self.data

    def _read_loop(self):
        buffer = bytearray()
        while self.running:
            try:
                if self.serial.in_waiting > 0:
                    chunk = self.serial.read(self.serial.in_waiting)
                    buffer.extend(chunk)
                    
                    while len(buffer) >= self.FRAME_MIN_LEN:
                        # 找帧头
                        header_idx = buffer.find(self.HEADER)
                        if header_idx == -1:
                            buffer.clear()
                            break
                        if header_idx > 0:
                            del buffer[:header_idx]
                        
                        if len(buffer) < self.FRAME_MIN_LEN:
                            break
                        
                        # 尝试匹配可能的帧长 (51, 91, 131)
                        parsed = False
                        for flen in [51, 91, 131]:
                            if len(buffer) < flen:
                                continue
                            
                            frame = buffer[:flen]
                            if frame[-1] != self.TAIL:
                                continue
                            
                            # 校验和
                            checksum = 0
                            for i in range(1, flen - 2):
                                checksum ^= frame[i]
                            
                            if checksum == frame[flen - 2]:
                                self._parse_frame(frame)
                                del buffer[:flen]
                                parsed = True
                                break
                        
                        if not parsed:
                            # 如果当前位置不是有效帧头，跳过1字节继续搜
                            del buffer[0]
                else:
                    time.sleep(0.001)
            except Exception as e:
                logger.error(f"Read error: {e}")
                time.sleep(1)

    def _parse_frame(self, frame):
        """解析 8 字节的摇杆/按键/板机数据"""
        try:
            # 数据负载从 index 1 开始
            # Left Joystick: 4 * int16 (Offset 0-7)
            # Right Joystick: 4 * int16 (Offset 8-15)
            payload = frame[1:-2]
            
            with self.lock:
                self.data.timestamp = time.time()
                for i in range(4):
                    self.data.left[i] = struct.unpack('<h', payload[i*2 : i*2+2])[0]
                    self.data.right[i] = struct.unpack('<h', payload[8+i*2 : 8+i*2+2])[0]
        except Exception as e:
            logger.error(f"Parse error: {e}")

if __name__ == "__main__":
    # 使用示例
    import sys
    port = "/dev/ttyACM14" if len(sys.argv) < 2 else sys.argv[1]
    
    reader = TriggerReader(port=port)
    try:
        reader.start()
        print("Reading trigger data... Press Ctrl+C to stop.")
        while True:
            data = reader.get_data()
            # print("\033[H\033[J") # 清屏 (可选)
            print(f"\r{data.left} | {data.right}", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        reader.stop()
        print("\nExit.")