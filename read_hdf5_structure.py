import h5py

def print_hdf5_structure(name, obj):
    if isinstance(obj, h5py.Dataset):
        print(f"[DATASET] {name}  shape={obj.shape}  dtype={obj.dtype}")
    elif isinstance(obj, h5py.Group):
        print(f"[GROUP]   {name}")

def inspect_hdf5(file_path):
    with h5py.File(file_path, "r") as f:
        print(f"\nFile: {file_path}\n")
        f.visititems(print_hdf5_structure)

if __name__ == "__main__":
    print("origin:")
    inspect_hdf5("./data/cover_blocks/demo_clean/data/episode0.hdf5")
    print()

    print("replay:")
    inspect_hdf5("./data/cover_blocks/x-one/data_replay/0.hdf5")
    print()

    print("after:")
    inspect_hdf5("./data/cover_blocks/x-one/data/episode0.hdf5")