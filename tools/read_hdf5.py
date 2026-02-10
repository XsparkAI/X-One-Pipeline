import os
import numpy as np
import matplotlib.pyplot as plt

from robot.utils.base.data_handler import hdf5_groups_to_dict


# ==========================
# Config
# ==========================
# DATA_PATH = "./0.hdf5"
DATA_PATH = "data/mobile_test/x-one-mobile-30hz/0.hdf5"
# DATA_PATH = "save_xxx/new/0.hdf5"
# DATA_PATH = "/mnt/nas/y1_real_data/redbao_stage1/10.hdf5"
SAVE_DIR = "save/timestamp_analysis"

CONTROLLER_KEY = ['left_arm', 'right_arm']
SENSOR_KEY = ['cam_head', 'cam_left_wrist', 'cam_right_wrist']

REF_KEY = 'left_arm'      # reference clock
TIME_UNIT = 1e6           # ns → ms

# ==========================
# Load data
# ==========================
episode = hdf5_groups_to_dict(DATA_PATH)
import pdb;pdb.set_trace()

os.makedirs(SAVE_DIR, exist_ok=True)

time_stamp = {}

for controller in CONTROLLER_KEY:
    time_stamp[controller] = np.asarray(episode[controller]['timestamp'])[5:-10]
    # print(time_stamp[controller][1])
for sensor in SENSOR_KEY:
    time_stamp[sensor] = np.asarray(episode[sensor]['timestamp'])[5:-10]
    # print(time_stamp[sensor][1])

time_stamp["avg_cam"] = np.asarray(episode["cam_head"]['timestamp'])[5:-10] + np.asarray(episode["cam_left_wrist"]['timestamp'])[5:-10] + np.asarray(episode["cam_right_wrist"]['timestamp'])[5:-10] 
time_stamp["avg_cam"] = time_stamp["avg_cam"]/3
# sanity check
lengths = {k: len(v) for k, v in time_stamp.items()}
assert len(set(lengths.values())) == 1, f"Timestamp length mismatch: {lengths}"

T = lengths[REF_KEY]
# ==========================
# Compute error
# ==========================
ref_ts = time_stamp[REF_KEY]

time_error = {}
for key, ts in time_stamp.items():
    if key == REF_KEY:
        continue
    time_error[key] = (ts - ref_ts) / TIME_UNIT  # ms


# ==========================
# Visualization
# ==========================
plt.figure(figsize=(12, 6))

for key, err in time_error.items():
    plt.plot(err, label=key, linewidth=1)

plt.axhline(0, color='black', linestyle='--', linewidth=0.8)

plt.xlabel("Frame index")
plt.ylabel("Time error (ms)")
plt.title(f"Timestamp alignment error (ref = {REF_KEY})")
plt.legend()
plt.grid(True)

save_path = os.path.join(SAVE_DIR, "timestamp_error_curve.png")
plt.tight_layout()
plt.savefig(save_path, dpi=200)
plt.close()

print(f"[OK] Saved timestamp error plot to: {save_path}")


# ==========================
# Optional: statistical summary
# ==========================
summary_path = os.path.join(SAVE_DIR, "timestamp_error_stats.txt")

with open(summary_path, "w") as f:
    for key, err in time_error.items():
        f.write(f"{key}:\n")
        f.write(f"  mean  = {err.mean():.3f} ms\n")
        f.write(f"  std   = {err.std():.3f} ms\n")
        f.write(f"  min   = {err.min():.3f} ms\n")
        f.write(f"  max   = {err.max():.3f} ms\n\n")

print(f"[OK] Saved timestamp stats to: {summary_path}")


