from robot.utils.base.data_handler import hdf5_groups_to_dict, get_files, get_item, dict_to_list, debug_print
from robot.utils.base.data_transform_pipeline import X_spark_format_pipeline
from robot.data.collect_any import CollectAny
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.load_file import load_yaml
import os
from pathlib import Path

if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Transform datasets typr to HDF5.')
    parser.add_argument('base_cfg', type=str,
                        help="your data dir like: datasets/task/")
    parser.add_argument('task_name', type=str,
                        help='task name under data_path/')
    parser.add_argument('new_task_name', type=str,
                        help='output path for transformed data')
    args = parser.parse_args()

    base_cfg_path = os.path.join(CONFIG_DIR, f"{args.base_cfg}.yml")
    base_cfg = load_yaml(base_cfg_path)

    task_name = args.task_name
    data_path = os.path.join(base_cfg["collect"]["save_dir"], task_name, base_cfg["collect"]["type"])
    new_task_name = args.new_task_name

    hdf5_paths = get_files(data_path, "*.hdf5")

    base_cfg["collect"]["task_name"] = new_task_name
    base_cfg["collect"]["move_check"] = False
    collection = CollectAny(config=base_cfg["collect"])

    collection._add_data_transform_pipeline(X_spark_format_pipeline)

    fail_episode_list = []
    for hdf5_path in hdf5_paths:
        try:
            debug_print("x_one", f"converting {hdf5_path}.", "INFO")
            episode = dict_to_list(hdf5_groups_to_dict(hdf5_path))
            for ep in episode:
                collection.collect(ep, None)
            collection.write(episode_id=Path(hdf5_path).stem)
        except Exception as e:
            debug_print("x_one", f"converting {hdf5_path} Fail: \n{e}", "ERROR")
            fail_episode_list.append(hdf5_path)
    
    output_path = os.path.join(base_cfg["collect"]["save_dir"], new_task_name, base_cfg["collect"]["type"])
    fail_save_path = Path(os.path.join(output_path, "fail_episodes.txt"))
    # ---------- 保存失败列表 ----------
    fail_save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(fail_save_path, "w", encoding="utf-8") as f:
        for p in fail_episode_list:
            f.write(str(p) + "\n")