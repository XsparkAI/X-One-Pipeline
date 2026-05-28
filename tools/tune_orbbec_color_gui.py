#!/usr/bin/env python3
"""GUI slider tool for live Orbbec color/ISP tuning."""

import argparse
import copy
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import numpy as np
from PIL import Image, ImageTk

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from robot.sensor.Orbbec_sensor import (
    COLOR_BOOL_SETTINGS,
    COLOR_SETTING_SPECS,
    DEFAULT_CAMERA_COLOR,
    OrbbecSensor,
    resolve_camera_color_settings,
)
from robot.utils.base.load_file import load_yaml

CAMERA_ROLES = ("head", "left_wrist", "right_wrist")
PREVIEW_SIZE = (160, 120)
SLIDER_LENGTH = 150
YAML_PREVIEW_HEIGHT = 4

SLIDER_SPECS = {
    "exposure": {"label": "Exposure (us)", "from": 1, "to": 500, "resolution": 1},
    "gain": {"label": "Gain", "from": 0, "to": 128, "resolution": 1},
    "white_balance": {"label": "White Balance (K)", "from": 2800, "to": 6500, "resolution": 50},
    "brightness": {"label": "Brightness", "from": -64, "to": 64, "resolution": 1},
    "contrast": {"label": "Contrast", "from": 0, "to": 100, "resolution": 1},
    "saturation": {"label": "Saturation", "from": 0, "to": 100, "resolution": 1},
    "hue": {"label": "Hue", "from": -180, "to": 180, "resolution": 1},
    "gamma": {"label": "Gamma", "from": 100, "to": 500, "resolution": 5},
    "sharpness": {"label": "Sharpness", "from": 0, "to": 100, "resolution": 1},
}

EXPORT_KEYS = tuple(COLOR_BOOL_SETTINGS.keys()) + tuple(COLOR_SETTING_SPECS.keys())


def _frame_stats(frame_rgb):
    mean = frame_rgb.reshape(-1, 3).mean(axis=0)
    return tuple(round(float(v), 1) for v in mean)


def _build_yaml_snippet(settings_by_role):
    head = settings_by_role["head"]
    lines = [
        "  CAMERA_COLOR:",
        f"    auto_exposure: {'true' if head['auto_exposure'] else 'false'}",
        f"    exposure: {head['exposure']}",
        f"    gain: {head['gain']}",
        f"    auto_white_balance: {'true' if head['auto_white_balance'] else 'false'}",
        f"    white_balance: {head['white_balance']}",
        f"    brightness: {head['brightness']}",
        f"    contrast: {head['contrast']}",
        f"    saturation: {head['saturation']}",
        f"    hue: {head['hue']}",
        f"    gamma: {head['gamma']}",
        f"    sharpness: {head['sharpness']}",
        "    by_camera:",
    ]
    for role in ("head", "left_wrist", "right_wrist"):
        role_settings = settings_by_role[role]
        overrides = {}
        for key in EXPORT_KEYS:
            if key in COLOR_BOOL_SETTINGS:
                continue
            if role_settings.get(key) != head.get(key):
                overrides[key] = role_settings[key]
        if role == "head" and overrides:
            lines.append("      head:")
            for key, value in overrides.items():
                lines.append(f"        {key}: {value}")
        elif role != "head" and overrides:
            lines.append(f"      {role}:")
            for key, value in overrides.items():
                lines.append(f"        {key}: {value}")
    return "\n".join(lines)


class OrbbecColorTunerApp:
    def __init__(self, cfg_path, match_slave=True):
        self.cfg_path = cfg_path
        self.match_slave = match_slave
        self.base_cfg = load_yaml(cfg_path)
        self.robot_config = self.base_cfg["robot"]
        self.serials = self.robot_config["CAMERA_SERIALS"]
        self.settings_by_role = {
            role: resolve_camera_color_settings(self.robot_config, role)
            for role in CAMERA_ROLES
        }
        for role in CAMERA_ROLES:
            self._ensure_defaults(self.settings_by_role[role])

        self.current_role = "head"
        self.sensors = {}
        self.preview_labels = {}
        self.preview_photos = {}
        self.preview_job = None
        self.apply_job = None
        self.slider_vars = {}
        self.slider_widgets = {}
        self.value_labels = {}
        self.auto_vars = {}
        self._updating_ui = False
        self._camera_lock = threading.Lock()

        self.root = tk.Tk()
        self.root.title("Orbbec Color Tuner")
        self.root.geometry("980x640")
        self.root.minsize(820, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()
        self.open_all_cameras()
        self.refresh_preview()

    def _ensure_defaults(self, settings):
        merged = {**DEFAULT_CAMERA_COLOR, **settings}
        for key in COLOR_BOOL_SETTINGS:
            merged[key] = bool(merged.get(key, DEFAULT_CAMERA_COLOR[key]))
        for key in COLOR_SETTING_SPECS:
            merged[key] = int(merged.get(key, DEFAULT_CAMERA_COLOR[key]))
        settings.clear()
        settings.update(merged)

    def _build_ui(self):
        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, padding=6)
        right = ttk.Frame(main, padding=6)
        main.add(left, weight=1)
        main.add(right, weight=2)

        preview_frame = ttk.LabelFrame(left, text="Live Preview", padding=4)
        preview_frame.pack(fill=tk.X, expand=False)
        preview_grid = ttk.Frame(preview_frame)
        preview_grid.pack(fill=tk.X)

        for col, role in enumerate(CAMERA_ROLES):
            cell = ttk.Frame(preview_grid, padding=2)
            cell.grid(row=0, column=col, sticky="n")
            preview_grid.columnconfigure(col, weight=1)

            title = ttk.Label(cell, text=role, font=("", 9, "bold"))
            title.pack(anchor=tk.CENTER)
            label = ttk.Label(cell)
            label.pack(pady=2)
            self.preview_labels[role] = label

        self.stats_var = tk.StringVar(value="mean_rgb: -")
        ttk.Label(
            preview_frame,
            textvariable=self.stats_var,
            wraplength=420,
            justify=tk.LEFT,
            font=("", 8),
        ).pack(anchor=tk.W, pady=(4, 0))
        mode_text = "3 cams + depth (start_slave-like)" if self.match_slave else "3 cams, color-only"
        ttk.Label(preview_frame, text=mode_text, font=("", 8)).pack(anchor=tk.W)

        selector = ttk.LabelFrame(right, text="Adjust parameters for", padding=4)
        selector.pack(fill=tk.X)
        self.role_var = tk.StringVar(value=self.current_role)
        role_row = ttk.Frame(selector)
        role_row.pack(fill=tk.X)
        for role in CAMERA_ROLES:
            ttk.Radiobutton(
                role_row,
                text=role,
                value=role,
                variable=self.role_var,
                command=self.on_role_changed,
            ).pack(side=tk.LEFT, padx=(0, 10))

        controls = ttk.LabelFrame(right, text="Parameters", padding=4)
        controls.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        canvas = tk.Canvas(controls, highlightthickness=0)
        scrollbar = ttk.Scrollbar(controls, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_controls_resize(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_controls_resize)

        auto_frame = ttk.Frame(scroll_frame)
        auto_frame.pack(fill=tk.X, pady=(0, 4))
        for key in COLOR_BOOL_SETTINGS:
            var = tk.BooleanVar(value=bool(self.settings_by_role[self.current_role][key]))
            self.auto_vars[key] = var
            ttk.Checkbutton(
                auto_frame,
                text=key,
                variable=var,
                command=lambda k=key: self.on_auto_toggle(k),
            ).pack(side=tk.LEFT, padx=(0, 8))

        for key, spec in SLIDER_SPECS.items():
            row = ttk.Frame(scroll_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=spec["label"], width=14).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=float(self.settings_by_role[self.current_role][key]))
            self.slider_vars[key] = var
            scale = tk.Scale(
                row,
                from_=spec["from"],
                to=spec["to"],
                resolution=spec["resolution"],
                orient=tk.HORIZONTAL,
                variable=var,
                command=lambda _value, k=key: self.on_slider_changed(k),
                length=SLIDER_LENGTH,
                sliderlength=12,
            )
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
            self.slider_widgets[key] = scale
            value_label = ttk.Label(row, width=6, anchor=tk.E)
            value_label.pack(side=tk.RIGHT)
            self.value_labels[key] = value_label

        btn_frame = ttk.Frame(right, padding=(0, 6, 0, 0))
        btn_frame.pack(fill=tk.X)
        buttons = [
            ("Read From Camera", self.read_from_camera),
            ("Reopen All Cameras", self.reopen_all_cameras),
            ("Copy Head -> Wrists", self.copy_head_to_wrists),
            ("Export YAML", self.export_yaml),
            ("Save YAML To Config", self.save_yaml_to_config),
        ]
        for idx, (text, command) in enumerate(buttons):
            ttk.Button(btn_frame, text=text, command=command).grid(
                row=idx // 2,
                column=idx % 2,
                sticky="ew",
                padx=2,
                pady=2,
            )
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        export_frame = ttk.LabelFrame(right, text="YAML Preview", padding=4)
        export_frame.pack(fill=tk.BOTH, expand=False, pady=(6, 0))
        self.export_text = scrolledtext.ScrolledText(
            export_frame,
            height=YAML_PREVIEW_HEIGHT,
            width=36,
            font=("TkFixedFont", 9),
        )
        self.export_text.pack(fill=tk.BOTH, expand=True)
        self.refresh_yaml_preview()
        self.sync_ui_from_settings()

    def current_settings(self):
        return self.settings_by_role[self.current_role]

    def current_sensor(self):
        return self.sensors.get(self.current_role)

    def on_role_changed(self):
        if self.apply_job is not None:
            self.root.after_cancel(self.apply_job)
            self.apply_job = None
        self.current_role = self.role_var.get()
        self.sync_ui_from_settings()

    def close_all_cameras(self):
        for sensor in self.sensors.values():
            sensor.cleanup()
        self.sensors = {}

    def _setup_sensor(self, role):
        settings = copy.deepcopy(self.settings_by_role[role])
        sensor = OrbbecSensor(f"cam_{role}")
        sensor.set_up(
            CAMERA_SERIAL=self.serials[role],
            is_depth=self.match_slave,
            is_jpeg=False,
            color_settings=settings,
        )
        sensor.set_collect_info(["color"])
        self.sensors[role] = sensor
        return settings

    def open_all_cameras(self):
        self.close_all_cameras()
        for role in CAMERA_ROLES:
            self._setup_sensor(role)

        with self._camera_lock:
            for _ in range(12):
                for role in CAMERA_ROLES:
                    self.sensors[role].get_image()
            for role in CAMERA_ROLES:
                self.sensors[role].apply_color_settings(
                    copy.deepcopy(self.settings_by_role[role])
                )
            for _ in range(5):
                for role in CAMERA_ROLES:
                    self.sensors[role].get_image()

    def reopen_all_cameras(self):
        if self.apply_job is not None:
            self.root.after_cancel(self.apply_job)
            self.apply_job = None
        self.open_all_cameras()

    def sync_ui_from_settings(self):
        self._updating_ui = True
        settings = self.current_settings()
        for key, var in self.auto_vars.items():
            var.set(bool(settings[key]))
        for key, var in self.slider_vars.items():
            var.set(float(settings[key]))
            self.value_labels[key].configure(text=str(int(settings[key])))
        self._update_slider_states()
        self._updating_ui = False

    def _update_slider_states(self):
        settings = self.current_settings()
        disabled = set()
        if settings.get("auto_exposure"):
            disabled.update(("exposure", "gain"))
        if settings.get("auto_white_balance"):
            disabled.add("white_balance")
        for key, widget in self.slider_widgets.items():
            widget.configure(state=(tk.DISABLED if key in disabled else tk.NORMAL))

    def on_auto_toggle(self, key):
        if self._updating_ui:
            return
        settings = self.current_settings()
        settings[key] = bool(self.auto_vars[key].get())
        self._update_slider_states()
        self.schedule_apply()

    def on_slider_changed(self, key):
        if self._updating_ui:
            return
        value = int(round(float(self.slider_vars[key].get())))
        self.value_labels[key].configure(text=str(value))
        self.current_settings()[key] = value
        self.schedule_apply()

    def schedule_apply(self):
        if self.apply_job is not None:
            self.root.after_cancel(self.apply_job)
        self.apply_job = self.root.after(80, self.apply_settings)

    def apply_settings(self):
        self.apply_job = None
        sensor = self.current_sensor()
        if sensor is None:
            return
        with self._camera_lock:
            sensor.apply_color_settings(copy.deepcopy(self.current_settings()))
        self.refresh_yaml_preview()

    def read_from_camera(self):
        sensor = self.current_sensor()
        if sensor is None:
            return
        device_settings = sensor.read_color_settings()
        settings = self.current_settings()
        for key in EXPORT_KEYS:
            if key in device_settings:
                settings[key] = device_settings[key]
        self.sync_ui_from_settings()
        self.refresh_yaml_preview()

    def copy_head_to_wrists(self):
        head = copy.deepcopy(self.settings_by_role["head"])
        for role in ("left_wrist", "right_wrist"):
            wrist = self.settings_by_role[role]
            for key in EXPORT_KEYS:
                if key in ("exposure", "gain"):
                    continue
                wrist[key] = head[key]
        messagebox.showinfo("Copy", "Copied head color/ISP settings to both wrists (kept wrist exposure/gain).")
        self.sync_ui_from_settings()
        self.apply_settings()
        for role in ("left_wrist", "right_wrist"):
            sensor = self.sensors.get(role)
            if sensor is not None:
                with self._camera_lock:
                    sensor.apply_color_settings(copy.deepcopy(self.settings_by_role[role]))

    def refresh_yaml_preview(self):
        snippet = _build_yaml_snippet(self.settings_by_role)
        self.export_text.delete("1.0", tk.END)
        self.export_text.insert(tk.END, snippet)

    def export_yaml(self):
        snippet = _build_yaml_snippet(self.settings_by_role)
        path = filedialog.asksaveasfilename(
            defaultextension=".yml",
            initialfile="camera_color_snippet.yml",
            filetypes=[("YAML", "*.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(snippet + "\n")
        messagebox.showinfo("Export", f"Saved snippet to:\n{path}")

    def save_yaml_to_config(self):
        if not messagebox.askyesno("Confirm", f"Update robot.CAMERA_COLOR in\n{self.cfg_path} ?"):
            return

        head = self.settings_by_role["head"]
        color_cfg = {
            "auto_exposure": bool(head["auto_exposure"]),
            "exposure": head["exposure"],
            "gain": head["gain"],
            "auto_white_balance": bool(head["auto_white_balance"]),
            "white_balance": head["white_balance"],
            "brightness": head["brightness"],
            "contrast": head["contrast"],
            "saturation": head["saturation"],
            "hue": head["hue"],
            "gamma": head["gamma"],
            "sharpness": head["sharpness"],
            "by_camera": {},
        }
        for role in CAMERA_ROLES:
            role_settings = self.settings_by_role[role]
            overrides = {}
            for key in EXPORT_KEYS:
                if key in COLOR_BOOL_SETTINGS:
                    continue
                if role_settings.get(key) != head.get(key):
                    overrides[key] = role_settings[key]
            if overrides:
                color_cfg["by_camera"][role] = overrides

        self.robot_config["CAMERA_COLOR"] = color_cfg
        self._write_yaml(self.cfg_path, self.base_cfg)
        messagebox.showinfo("Saved", f"Updated {self.cfg_path}")

    def _write_yaml(self, path, data):
        import yaml

        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

    def _capture_preview_frame(self, role):
        sensor = self.sensors.get(role)
        if sensor is None:
            return None
        with self._camera_lock:
            image = sensor.get_image()
        frame = image.get("color")
        if frame is None or not isinstance(frame, np.ndarray) or frame.ndim != 3:
            return None
        return frame

    def refresh_preview(self):
        stats_lines = []
        try:
            for role in CAMERA_ROLES:
                frame = self._capture_preview_frame(role)
                label = self.preview_labels.get(role)
                if frame is None or label is None:
                    continue
                rgb = Image.fromarray(frame).resize(PREVIEW_SIZE, Image.Resampling.NEAREST)
                photo = ImageTk.PhotoImage(image=rgb)
                label.configure(image=photo)
                self.preview_photos[role] = photo
                mean = _frame_stats(frame)
                stats_lines.append(f"{role}: ({mean[0]}, {mean[1]}, {mean[2]})")
            if stats_lines:
                self.stats_var.set("mean_rgb  " + " | ".join(stats_lines))
        except Exception as exc:
            self.stats_var.set(f"Preview error: {exc}")
        self.preview_job = self.root.after(50, self.refresh_preview)

    def on_close(self):
        if self.preview_job is not None:
            self.root.after_cancel(self.preview_job)
        if self.apply_job is not None:
            self.root.after_cancel(self.apply_job)
        self.close_all_cameras()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Orbbec color tuning GUI")
    parser.add_argument(
        "--cfg",
        default=os.path.join(ROOT, "config", "x-one-piperX-orbbec.yml"),
        help="Robot config yaml path",
    )
    parser.add_argument(
        "--color-only",
        action="store_true",
        help="Open color stream only (differs from start_slave.sh)",
    )
    args = parser.parse_args()
    app = OrbbecColorTunerApp(args.cfg, match_slave=not args.color_only)
    app.run()


if __name__ == "__main__":
    main()
