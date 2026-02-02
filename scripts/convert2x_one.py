from hardware.utils.base.data_handler import hdf5_groups_to_dict, get_files, get_item, dict_to_list, debug_print
from hardware.utils.base.data_transform_pipeline import X_one_format_pipeline
from hardware.data.collect_any import CollectAny
import os
from pathlib import Path

if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Transform datasets typr to HDF5.')
    parser.add_argument('data_path', type=str,
                        help="your data dir like: datasets/task/")
    parser.add_argument('outout_path', type=str,
                        help='output path commanded like datasets/RDT/...')
    parser.add_argument('task_name', type=str,
                        help='task name under data_path/')
    args = parser.parse_args()
    data_path = args.data_path
    output_path = args.outout_path
    task_name = args.task_name

    data_path = os.path.join(data_path, task_name)
    hdf5_paths = get_files(data_path, "*.hdf5")
    condition = {
        "save_path": output_path,
        "task_name": task_name,
        "save_freq": 30, 
    }
    collection = CollectAny(condition=condition, move_check=False)
    collection._add_data_transform_pipeline(X_one_format_pipeline)

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
    
    fail_save_path = Path(os.path.join(output_path, task_name, "fail_episodes.txt"))
    # ---------- 保存失败列表 ----------
    fail_save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(fail_save_path, "w", encoding="utf-8") as f:
        for p in fail_episode_list:
            f.write(str(p) + "\n")