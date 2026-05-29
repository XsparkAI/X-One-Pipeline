from robot.utils.base.data_handler import hdf5_groups_to_dict, get_files, get_item, dict_to_list, debug_print
from robot.utils.base.data_transform_pipeline import X_spark_format_pipeline
from robot.data.collect_any import CollectAny
from robot.config._GLOBAL_CONFIG import CONFIG_DIR
from robot.utils.base.load_file import load_yaml
import os
from pathlib import Path
import argparse
import json
from tqdm import tqdm
from functools import partial
from multiprocessing import Pool, cpu_count

DATA_MAP = {
    "fix_frame_interval": "Pull the bag in front of you.",
    "grasp_frame_interval": "Grasp the zipper.",
    "pull_frame_interval": "Pull the zipper open.",
    "reset_frame_interval": "Reset the robotic arm."
}

def process_episode(hdf5_path, base_cfg):
    try:
        # 每一个进程需要独立的 CollectAny 实例（如果它包含不可序列化的状态或写锁）
        # 这里在函数内部初始化以确保进程安全
        local_cfg = base_cfg.copy()
        local_cfg["collect"]["move_check"] = False
        collection = CollectAny(config=local_cfg["collect"])
        collection._add_data_transform_pipeline(X_spark_format_pipeline)
        
        # debug_print("x_one", f"converting {hdf5_path}.", "INFO")
        episode = dict_to_list(hdf5_groups_to_dict(hdf5_path))
        for ep in episode:
            collection.collect(ep, None)

        # 读取同文件目录下, 结尾换为.json的文件, 获取其中的指令和子任务信息, 添加到collection中
        json_path = hdf5_path.replace(".hdf5", ".json")
        instructions = ["Open the bag."]
        subtasks = []

        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                if isinstance(json_data, list) and len(json_data) > 0:
                    config_item = json_data[0]
                    
                    for key, desc in DATA_MAP.items():
                        if key in config_item:
                            start, end = config_item[key]
                            subtasks.append([(start, end), desc])
                else:
                    debug_print("x_one", f"No valid data in {json_path}. Using default instructions.", "WARNING")

        collection.add_extra_episode_info({"instructions": instructions})
        collection.add_extra_episode_info({"subtasks": subtasks})
        
        collection.add_extra_episode_info({"additional_info": {"frequency": 30}, "data_format_version": "v1.0"})
        
        collection.write(episode_id=Path(hdf5_path).stem)
        return None
    except Exception as e:
        debug_print("x_one", f"converting {hdf5_path} Fail: \n{e}", "ERROR")
        return hdf5_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Transform datasets typr to HDF5.')
    parser.add_argument('base_cfg', type=str,
                        help="your data dir like: datasets/task/")
    parser.add_argument('task_name', type=str,
                        help='task name under data_path/')
    parser.add_argument('new_task_name', type=str,
                        help='output path for transformed data')
    parser.add_argument('--num_workers', type=int, default=12,
                        help='number of parallel workers.')
    parser.add_argument('--save_dir', type=str, default=None,
                        help='directory to save transformed data.')
    args = parser.parse_args()

    base_cfg_path = os.path.join(CONFIG_DIR, f"{args.base_cfg}.yml")
    base_cfg = load_yaml(base_cfg_path)
    
    task_name = args.task_name
    data_path = os.path.join(base_cfg["collect"]["save_dir"], task_name, base_cfg["collect"]["type"])
    
    new_task_name = args.new_task_name

    hdf5_paths = get_files(data_path, "*.hdf5")

    if args.save_dir is not None:
        base_cfg["collect"]["save_dir"] = args.save_dir

    base_cfg["collect"]["task_name"] = new_task_name
    
    num_workers = min(args.num_workers, len(hdf5_paths))
    debug_print("x_one", f"Starting parallel processing with {num_workers} workers...", "INFO")

    # 使用进程池并行处理
    results = []
    with Pool(num_workers) as pool:
        process_func = partial(process_episode, base_cfg=base_cfg)
        
        # 使用 imap_unordered 并包装 tqdm 以实现实时更新
        for res in tqdm(pool.imap_unordered(process_func, hdf5_paths), 
                       total=len(hdf5_paths), 
                       desc="Converting episodes"):
            results.append(res)

    # 过滤出失败的任务
    fail_episode_list = [res for res in results if res is not None]
    
    output_path = os.path.join(base_cfg["collect"]["save_dir"], new_task_name, base_cfg["collect"]["type"])
    fail_save_path = Path(os.path.join(output_path, "fail_episodes.txt"))
    # ---------- 保存失败列表 ----------
    fail_save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(fail_save_path, "w", encoding="utf-8") as f:
        for p in fail_episode_list:
            f.write(str(p) + "\n")