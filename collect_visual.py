# -*- coding: utf-8 -*-
"""
Data Collection UI (No OpenGL)
Using: PyQt5 + Matplotlib (3D view) + PyQtGraph (image display)
"""

import sys
sys.path.append("./")

import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
import cv2

import os
import glob
import json
import time
from datetime import datetime
# os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms'
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/home/xspark-ai/miniconda3/envs/Xone/lib/qt5/plugins/platforms"

class StopWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal()

    def __init__(self, robot, is_save=False, is_reset=True):
        super().__init__()
        self.robot = robot
        self.is_save = is_save
        self.is_reset = is_reset

    def run(self):
        if self.is_save:
            self.robot.finish()
        
        if self.is_reset or self.robot.first_start:
            self.robot.reset()
            self.robot.first_start = False

        self.robot.clean()

        self.finished.emit()

class MoveWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    
    def __init__(self, robot, move_data):
        super().__init__()
        self.robot = robot
        self.move_data = move_data

    def run(self):
        self.robot.change_mode(teleop=False)
        self.robot.move(self.move_data)
        time.sleep(2)
        self.robot.change_mode(teleop=True)
        self.finished.emit()

class DataCollectorUI(QtWidgets.QWidget):
    def __init__(self, robot):
        super().__init__()
        self.setWindowTitle("Data Collection UI — No OpenGL Version")
        self.is_running = False
        self.robot = robot
        self.robot.first_start = True
        self.robot.change_mode(teleop=False)
        
        # Data collection metadata
        self.data_type = "Normal"  # Normal or Trial
        self.worker_name = ""  # Worker name
        self.head_zoom = 1.0
        
        # Layout
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # --- 0. Top Bar (Reload Cameras + Normal/Trial Toggle) ---
        top_bar_layout = QtWidgets.QHBoxLayout()
        
        # Left: Reload Cameras button
        self.btn_reload_cameras = QtWidgets.QPushButton("Reload Cameras")
        self.btn_reload_cameras.setFixedSize(140, 35)
        self.btn_reload_cameras.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #607D8B;
                color: white;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
        """)
        # Leave connection empty for user to implement
        # self.btn_reload_cameras.clicked.connect(self.reload_cameras)
        top_bar_layout.addWidget(self.btn_reload_cameras)
        
        # Head Crop Button
        self.btn_crop_head = QtWidgets.QPushButton("Head Zoom: 1.0X")
        self.btn_crop_head.setFixedSize(140, 35)
        self.btn_crop_head.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #607D8B;
                color: white;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
        """)
        self.btn_crop_head.clicked.connect(self.cycle_head_zoom)
        top_bar_layout.addWidget(self.btn_crop_head)

        top_bar_layout.addStretch()
        
        # Info Label (Task | Worker | Stats)
        self.lbl_info = QtWidgets.QLabel("Task: None | Worker: None | Today: 0.00h")
        self.lbl_info.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976D2;")
        self.lbl_info.setAlignment(QtCore.Qt.AlignCenter)
        top_bar_layout.addWidget(self.lbl_info)

        top_bar_layout.addStretch()
        
        # Right: Current collection type label and toggle button
        type_label = QtWidgets.QLabel("当前采集: ")
        type_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        top_bar_layout.addWidget(type_label)
        
        # Toggle button for Normal/Trial
        self.btn_toggle_type = QtWidgets.QPushButton("Normal")
        self.btn_toggle_type.setFixedSize(100, 35)
        self.btn_toggle_type.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #4CAF50;
                color: white;
            }
        """)
        self.btn_toggle_type.clicked.connect(self.toggle_data_type)
        top_bar_layout.addWidget(self.btn_toggle_type)
        
        main_layout.addLayout(top_bar_layout)

        # --- 1. Camera Views (Top, 2/3 height) ---
        cam_layout = QtWidgets.QHBoxLayout()
        
        self.img_main = pg.ImageView()
        self.img_wrist1 = pg.ImageView()
        self.img_wrist2 = pg.ImageView()
        
        # Clean up image views
        for img in [self.img_main, self.img_wrist1, self.img_wrist2]:
            img.ui.histogram.hide()
            img.ui.roiBtn.hide()
            img.ui.menuBtn.hide()

        def add_cam(layout, label, img):
            v = QtWidgets.QVBoxLayout()
            lbl = QtWidgets.QLabel(label)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            v.addWidget(lbl)
            v.addWidget(img)
            layout.addLayout(v, stretch=1)

        # Order: Left Wrist, Head, Right Wrist
        add_cam(cam_layout, "Left Wrist", self.img_wrist1)
        add_cam(cam_layout, "Head", self.img_main)
        add_cam(cam_layout, "Right Wrist", self.img_wrist2)
        
        main_layout.addLayout(cam_layout, stretch=2)

        # --- 2. Buttons (Bottom, 1/3 height) ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_next = QtWidgets.QPushButton("Next")
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_abort = QtWidgets.QPushButton("Abort")
        
        # Right side: Set Dataset and Set Worker (stacked)
        right_btn_layout = QtWidgets.QVBoxLayout()
        self.btn_set_dataset = QtWidgets.QPushButton("Set Dataset")
        self.btn_set_worker = QtWidgets.QPushButton("Set Worker")
        
        # Button Style & Size
        base_style = "font-size: 24px; font-weight: bold; border-radius: 12px; margin: 5px;"
        disabled_style = "QPushButton:disabled { background-color: #A9A9A9; color: #E0E0E0; }"

        for btn in [self.btn_start, self.btn_next, self.btn_stop, self.btn_abort]:
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        for btn in [self.btn_set_dataset, self.btn_set_worker]:
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        def set_style(btn, color):
            btn.setStyleSheet(f"""
                QPushButton {{
                    {base_style}
                    background-color: {color};
                    color: white;
                }}
                {disabled_style}
            """)

        set_style(self.btn_start, "#4CAF50")
        set_style(self.btn_next, "#50188C")
        set_style(self.btn_stop, "#f44336")
        set_style(self.btn_abort, "#FF9800")
        set_style(self.btn_set_dataset, "#2196F3")
        set_style(self.btn_set_worker, "#9C27B0")
        
        right_btn_layout.addWidget(self.btn_set_dataset)
        right_btn_layout.addWidget(self.btn_set_worker)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_next)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_abort)
        btn_layout.addLayout(right_btn_layout)
        
        main_layout.addLayout(btn_layout, stretch=1)

        # Connections
        self.btn_start.clicked.connect(self.start_capture)
        self.btn_next.clicked.connect(self.next_capture)
        self.btn_stop.clicked.connect(self.stop_capture)
        self.btn_abort.clicked.connect(self.abort_capture)
        self.btn_set_dataset.clicked.connect(self.set_dataset)
        self.btn_set_worker.clicked.connect(self.set_worker)
        self.btn_reload_cameras.clicked.connect(self.reload_cameras)

        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_views)

        # Initial State: Only Set Dataset enabled
        self.set_initial_state(dataset_set=False)
        
        # Auto-open set dataset
        QtCore.QTimer.singleShot(100, self.set_dataset)
        
        # Show maximized to fit screen
        self.showMaximized()

    def set_initial_state(self, dataset_set=False):
        if not dataset_set:
            self.btn_start.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_abort.setEnabled(False)
            self.btn_set_dataset.setEnabled(True)
            self.btn_set_worker.setEnabled(True)
            self.btn_crop_head.setEnabled(True)
        else:
            # Start only enabled if both dataset and worker are set
            can_start = bool(self.worker_name)
            self.btn_start.setEnabled(can_start)
            self.btn_next.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_abort.setEnabled(True)
            self.btn_set_dataset.setEnabled(True)
            self.btn_set_worker.setEnabled(True)
            self.btn_crop_head.setEnabled(True)

    def set_capture_state(self):
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_abort.setEnabled(True)
        self.btn_set_dataset.setEnabled(False)
        self.btn_set_worker.setEnabled(False)
        self.btn_crop_head.setEnabled(False)

    def show_message(self, title, text, timeout=2000):
        self.msg = QtWidgets.QMessageBox(self)
        self.msg.setWindowTitle(title)
        self.msg.setText(text)
        self.msg.setStandardButtons(QtWidgets.QMessageBox.NoButton)
        self.msg.setWindowModality(QtCore.Qt.NonModal)
        self.msg.show()
        QtCore.QTimer.singleShot(timeout, self.msg.accept)

    def update_stats(self):
        """Update the top info label with Task, Worker and daily collected hours"""
        task_name = self.robot.collector.config.get("task_name", "None")
        # Ensure task_name is not empty string, otherwise show None
        if not task_name:
            task_name = "None"
            
        worker_name = self.worker_name if self.worker_name else "None"
        hours = 0.0

        if self.worker_name and task_name != "None":
            save_path = self.robot.collector.config["save_dir"]
            dataset_path = os.path.join(save_path, task_name)
            ratings_file = os.path.join(dataset_path, "ratings.json")
            
            total_frames = 0
            today_str = datetime.now().strftime("%Y-%m-%d")

            if os.path.exists(ratings_file):
                try:
                    with open(ratings_file, 'r', encoding='utf-8') as f:
                        ratings = json.load(f)
                    
                    for key, val in ratings.items():
                        # Check worker
                        if val.get("worker") != self.worker_name:
                            continue
                        
                        # Check date
                        ts = val.get("timestamp", "")
                        if not ts.startswith(today_str):
                            continue
                            
                        total_frames += val.get("frames", 0)
                except Exception as e:
                    print(f"Error reading ratings for stats: {e}")
            
            # Calculate hours: fps=30
            hours = total_frames / 30 / 3600
            
        self.lbl_info.setText(f"Task: {task_name} | Worker: {worker_name} | Today: {hours:.2f}h")

    # ------------ Core Logic ------------
    def cycle_head_zoom(self):
        zooms = [1.0, 1.5, 2.0, 2.5, 3.0]
        try:
            idx = zooms.index(self.head_zoom)
            next_idx = (idx + 1) % len(zooms)
            self.head_zoom = zooms[next_idx]
        except ValueError:
            self.head_zoom = 1.0
        
        self.btn_crop_head.setText(f"Head Zoom: {self.head_zoom}X")

    def toggle_data_type(self):
        """Toggle between Normal and Trial"""
        if self.data_type == "Normal":
            self.data_type = "Trial"
            self.btn_toggle_type.setText("Trial")
            self.btn_toggle_type.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    border-radius: 8px;
                    background-color: #FF9800;
                    color: white;
                }
            """)
        else:
            self.data_type = "Normal"
            self.btn_toggle_type.setText("Normal")
            self.btn_toggle_type.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    border-radius: 8px;
                    background-color: #4CAF50;
                    color: white;
                }
            """)
    
    def set_worker(self):
        """Set the worker name from a list"""
        workers = ["Fan Jinming", "Lu Lian", "Tan Xu"]
        worker, ok = QtWidgets.QInputDialog.getItem(
            self, "Set Worker", "Select Worker:", workers, 0, False
        )
        if ok and worker:
            self.worker_name = worker
            print(f"Worker set to: {worker}")
            self.show_message("Info", f"Worker: {worker}", 2000)
            self.update_stats()
            # Update button state
            self.set_initial_state(dataset_set=True)
    
    def set_dataset(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Set Dataset", "Dataset Name:")
        if ok and text:
            # Update robot condition
            self.robot.collector.config["task_name"] = text
            
            # Ensure directory exists
            save_path = self.robot.collector.config["save_dir"]
            dataset_path = os.path.join(save_path, text)
            if not os.path.exists(dataset_path):
                os.makedirs(dataset_path, exist_ok=True)
            
            # Find next episode index
            files = glob.glob(os.path.join(dataset_path, "*.hdf5"))
            max_idx = -1
            for f in files:
                try:
                    base = os.path.basename(f)
                    idx = int(os.path.splitext(base)[0])
                    if idx > max_idx:
                        max_idx = idx
                except ValueError:
                    pass
            
            self.robot.collector.episode_index = max_idx + 1
            print(f"Dataset set to: {text}, Next Episode ID: {self.robot.collector.episode_index}")
            
            self.update_stats()
            self.set_initial_state(dataset_set=True)

    def next_capture(self):
        if not self.is_running:
            print("is_running=False")
            return
        
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self.btn_set_dataset.setEnabled(False)
        self.btn_set_worker.setEnabled(False)
        
        move_data = {
            "arm":{
                "left_arm": {
                    "joint": [-1.10, -1.27, 0.44, 0.87, -1.0, 1.55],
                },
                "right_arm":{
                    "joint": [0.0, -1.47, 0.56, 0.71, -1.56, -0.33],
                },
            },
        }

        self.next_worker = MoveWorker(self.robot, move_data)
        self.next_worker.finished.connect(self.on_next_finished)
        self.next_worker.start()
        self.timer.start(33)  # 10 Hz
    
    def on_next_finished(self):
        self.set_capture_state()
        self.show_message("Info", "Move finished!", 2000)

    def start_capture(self):
        if self.is_running:
            return
        
        self.robot.collector.episode = []
        
        # Disable all during save
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self.btn_set_dataset.setEnabled(False)
        self.btn_set_worker.setEnabled(False)

        self.robot.change_mode(teleop=False)
        self.stop_worker = StopWorker(self.robot, is_save=False, is_reset=False)
        self.stop_worker.finished.connect(self.on_start_finished)
        self.stop_worker.start()
        self.timer.start(33)  # 10 Hz

    def on_start_finished(self):
        self.is_running = True
        self.set_capture_state()
        self.show_message("Info", "Start processing finished!", 2000)
        self.robot.change_mode(teleop=True)
        self.robot.start()

    def stop_capture(self):
        if not self.is_running:
            return
        self.is_running = False
        # Disable all during save
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self.btn_set_dataset.setEnabled(False)
        self.btn_set_worker.setEnabled(False)

        # Store frame count before saving/clearing
        self.last_episode_frames = len(self.robot.collector.episode)
        
        self.robot.change_mode(teleop=False)
        self.stop_worker = StopWorker(self.robot, is_save=True, is_reset=True)
        self.stop_worker.finished.connect(self.on_stop_finished)
        self.stop_worker.start()

    def on_stop_finished(self):
        # Save metadata to ratings.json
        self.save_ratings_json()
        self.update_stats()
        self.set_initial_state(dataset_set=True)
        self.show_message("Info", "Stop processing finished!", 2000)
    
    def save_ratings_json(self):
        """Save episode metadata to ratings.json"""
        save_path = self.robot.collector.config["save_dir"]
        task_name = self.robot.collector.config["task_name"]
        dataset_path = os.path.join(save_path, task_name)
        ratings_file = os.path.join(dataset_path, "ratings.json")
        
        # Load existing ratings or create new
        if os.path.exists(ratings_file):
            with open(ratings_file, 'r', encoding='utf-8') as f:
                ratings = json.load(f)
        else:
            ratings = {}
        
        # Get the current episode index (the one that was just saved)
        episode_idx = self.robot.collector.episode_index - 1
        file_name = f"{episode_idx}.hdf5"
        
        # Add new entry
        ratings[file_name] = {
            "type": self.data_type,
            "worker": self.worker_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "frames": getattr(self, "last_episode_frames", 0)
        }
        
        # Save back to file
        with open(ratings_file, 'w', encoding='utf-8') as f:
            json.dump(ratings, f, indent=4, ensure_ascii=False)
        
        print(f"Saved ratings for {file_name}: type={self.data_type}, worker={self.worker_name}")
    
    def remove_from_ratings_json(self, file_name):
        """Remove episode metadata from ratings.json"""
        save_path = self.robot.collector.config["save_dir"]
        task_name = self.robot.collector.config["task_name"]
        dataset_path = os.path.join(save_path, task_name)
        ratings_file = os.path.join(dataset_path, "ratings.json")
        
        # Load existing ratings
        if os.path.exists(ratings_file):
            with open(ratings_file, 'r', encoding='utf-8') as f:
                ratings = json.load(f)
            
            # Remove the entry if it exists
            if file_name in ratings:
                del ratings[file_name]
                
                # Save back to file
                with open(ratings_file, 'w', encoding='utf-8') as f:
                    json.dump(ratings, f, indent=4, ensure_ascii=False)
                
                print(f"Removed ratings for {file_name}")
            else:
                print(f"Rating entry for {file_name} not found in ratings.json")
        else:
            print(f"ratings.json not found at {ratings_file}")

    def abort_capture(self):
        if self.is_running:
            # Discard current
            self.is_running = False
            # self.timer.stop()
            # self.robot.collector.episode = []
            
            # Reset robot
            self.robot.first_start =True
            self.stop_worker = StopWorker(self.robot, is_save=False, is_reset=True)
            self.stop_worker.finished.connect(self.on_abort_reset_finished)
            self.stop_worker.start()
            
            # Disable buttons while resetting
            self.btn_start.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_abort.setEnabled(False)
            self.btn_set_dataset.setEnabled(False)
            self.btn_set_worker.setEnabled(False)
            
        # else:
        # Discard previous
        idx = self.robot.collector.episode_index - 1
        if idx < 0:
            self.show_message("Warning", "No previous data to discard!", 2000)
            return
        
        save_path = self.robot.collector.config["save_dir"]
        task_name = self.robot.collector.config["task_name"]
        file_path = os.path.join(save_path, task_name, f"{idx}.hdf5")
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                # Also remove from ratings.json
                self.remove_from_ratings_json(f"{idx}.hdf5")
                self.robot.collector.episode_index = idx
                self.update_stats()
                self.show_message("Info", f"Discarded episode {idx}", 2000)
            except Exception as e:
                self.show_message("Error", f"Failed to delete: {e}", 2000)
        else:
            self.show_message("Warning", f"File not found: {idx}.hdf5", 2000)

    def on_abort_reset_finished(self):
        self.set_initial_state(dataset_set=True)
        self.show_message("Info", "Aborted and Reset!", 2000)

    def update_views(self):
        data = self.robot.get_obs()

        self.update_images(data[1])

    # ------------ UI Update ------------
    def update_images(self, data):
        def decode(data):
            # If already a numpy array, return directly (TEST_MODE)
            if isinstance(data, np.ndarray):
                return data
            
            jpeg_bytes = data # .tobytes().rstrip(b"\0")
            nparr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            return cv2.imdecode(nparr, 1)
        cam_head = data["cam_head"]["color"]
        cam_left_wrist = data["cam_left_wrist"]["color"]
        cam_right_wrist = data["cam_right_wrist"]["color"]
        try:
            cam_head = decode(cam_head)
            cam_left_wrist = decode(cam_left_wrist)
            cam_right_wrist = decode(cam_right_wrist)
        except:
            print("cam type ERROR!")
            return

        cam_head = np.transpose(cam_head, (1, 0, 2)) 
        cam_left_wrist = np.transpose(cam_left_wrist, (1, 0, 2)) 
        cam_right_wrist = np.transpose(cam_right_wrist, (1, 0, 2)) 
        
        # Head: Manual Range for Zoom (ViewBox)
        self.img_main.setImage(cam_head, autoRange=False)
        
        # Calculate Range based on zoom
        w, h = cam_head.shape[0], cam_head.shape[1]
        center_w, center_h = w / 2, h / 2
        span_w = w / self.head_zoom
        span_h = h / self.head_zoom
        
        self.img_main.getView().setRange(
            xRange=(center_w - span_w/2, center_w + span_w/2),
            yRange=(center_h - span_h/2, center_h + span_h/2),
            padding=0
        )

        self.img_wrist1.setImage(cam_left_wrist)
        self.img_wrist2.setImage(cam_right_wrist)
    
    def reload_cameras(self):
        """Reload camera devices"""
        self.robot.reload_cameras()
        self.show_message("Info", "Cameras reloaded!", 1000)

# ------------ Mock Robot for Testing ------------
class MockCollection:
    def __init__(self):
        self.episode = []
        self.episode_index = 0
        self.condition = {
            "save_path": "./save/",
            "task_name": "abc"
        }

class MockRobot:
    def __init__(self):
        self.collection = MockCollection()
        self.first_start = True

    def set_up(self, teleop=True):
        print("Mock Robot Setup (No Hardware Connected)")

    def reset(self):
        print("Mock Robot Reset")

    def finish(self):
        self.collection.episode_index += 1
        print("Mock Robot Finish")

    def get(self):
        # Generate random noise images (480x640 RGB)
        h, w = 480, 640
        img_head = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        img_left = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        img_right = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        
        images = {
            "cam_head": {"color": img_head},
            "cam_left_wrist": {"color": img_left},
            "cam_right_wrist": {"color": img_right},
        }
        return [None, images]

    def collect(self, data):
        pass
    def change_mode(self, teleop=True):
        pass

# ------------ Main ------------
if __name__ == '__main__':
    # Set to True to test without hardware
    TEST_MODE = False
    
    if TEST_MODE:
        robot = MockRobot()
    else:
        # from my_robot.xspark_robot_node import XsparkRobotNode
        # robot = XsparkRobotNode()
        from robot.robot import get_robot
        from robot.utils.base.load_file import load_yaml
        robot_cfg = load_yaml("config/robot/x-one.yml")
        collect_cfg = load_yaml("config/collect/collect_sample.yml")
        robot = get_robot(robot_cfg)
        robot.collect_init(collect_cfg)
    
    robot.set_up(teleop=True)

    app = QtWidgets.QApplication(sys.argv)
    ui = DataCollectorUI(robot)
    ui.show()
    sys.exit(app.exec_())
