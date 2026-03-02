import h5py
import json


def read_frame_in_hdf5(file_path):
    with h5py.File(file_path, "r") as f:
        num_frames = f["cam_head/color"].shape[0]
        return num_frames

def read_frame_in_language_annotation_json(json_path, episode_idx):
    with open(json_path, "r") as f:
        data = json.load(f)

    episode_name = "episode_"+ str(episode_idx)
    if episode_name not in data:
        raise ValueError(f"{episode_name} 不存在")

    total_frames = sum(item[1] for item in data[episode_name])
    return total_frames

if __name__ == "__main__":

    is_all_same = True
    total_epsisodes = 100
    for episode_idx in range(total_epsisodes):
        print(episode_idx)
        frame_in_hdf5 = read_frame_in_hdf5(f"./data/cover_blocks/x-one/data_replay/{episode_idx}.hdf5")
        frame_in_json = read_frame_in_language_annotation_json("./data/cover_blocks/x-one/language_annotation.json", episode_idx)
        print(f"frame_in_hdf5: {frame_in_hdf5}")
        print(f"frame_in_json: {frame_in_json}")
        if frame_in_hdf5 != frame_in_json:
            is_all_same = False
            print("False")
    if is_all_same:
        print("True")