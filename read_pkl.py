import pickle
import numpy as np
import os

file_path = "/home/xspark-ai/project/RoboTwin/data/place_shoe/demo_clean/_traj_data/episode0.pkl"

if not os.path.exists(file_path):
    raise FileNotFoundError(file_path)

with open(file_path, "rb") as f:
    data = pickle.load(f)

print("=" * 80)
print("Loaded type:", type(data))
print("=" * 80)

# 情况 1：如果是 dict（最常见）
if isinstance(data, dict):
    for key, value in data.items():
        print(f"\n🔹 Key: {key}")
        print("Type:", type(value))

        # numpy array
        if isinstance(value, np.ndarray):
            print("Shape:", value.shape)
            print("First 10 entries:")
            print(value[:10])

        # # torch tensor
        # elif isinstance(value, torch.Tensor):
        #     print("Shape:", tuple(value.shape))
        #     print("First 10 entries:")
        #     print(value[:10])

        # list
        elif isinstance(value, list):
            print("Length:", len(value))
            print("First 10 elements:")
            # print(value[:2])
            print(len(value))

        else:
            print("Value preview:")
            print(value)

# 情况 2：如果是 list（每个元素是一条 step）
elif isinstance(data, list):
    print("Total length:", len(data))
    print("\nFirst 10 elements:\n")
    for i in range(min(10, len(data))):
        print(f"Index {i}:")
        print(data[i])
        print("-" * 40)

else:
    print("Unsupported data structure:")
    print(data)

print("=" * 80)