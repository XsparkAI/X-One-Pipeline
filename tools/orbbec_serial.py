import sys


def find_connected_orbbec_devices():
    try:
        import pyorbbecsdk
    except ImportError as exc:
        raise RuntimeError(
            "Failed to import pyorbbecsdk. Please activate the Xone conda environment first."
        ) from exc

    ctx = pyorbbecsdk.Context()
    devices = ctx.query_devices()
    count = devices.get_count()

    if count == 0:
        print("No Orbbec device detected.")
        return

    print(f"Detected {count} Orbbec device(s).")

    for index in range(count):
        print(f"\n device {index + 1}:")
        print(f"  name: {devices.get_device_name_by_index(index)}")
        print(f"  serial: {devices.get_device_serial_number_by_index(index)}")
        print(f"  uid: {devices.get_device_uid_by_index(index)}")
        print(f"  connection: {devices.get_device_connection_type_by_index(index)}")


if __name__ == "__main__":
    try:
        find_connected_orbbec_devices()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)