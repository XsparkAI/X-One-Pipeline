import json
import numpy as np
from typing import Any
import base64
import numpy as np
from typing import Any, Mapping

try:
    import torch

    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False


def _to_numpy(obj: Any) -> Any:
    if _HAS_TORCH and isinstance(obj, torch.Tensor):
        # 兼容 CUDA/半精度，先转 CPU 再转 numpy
        return obj.detach().cpu().numpy()
    if isinstance(obj, np.generic):
        # numpy 标量转成 Python 标量，避免 json 报错
        return obj.item()
    if isinstance(obj, Mapping):
        return {k: _to_numpy(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_numpy(v) for v in obj]
    return obj


def numpy_to_json(data: Any) -> str:
    cleaned = _to_numpy(data)
    return json.dumps(cleaned, cls=NumpyEncoder, ensure_ascii=False)


def json_to_numpy(json_str: str) -> Any:

    def object_hook(dct):
        if "__numpy_array__" in dct:
            data = base64.b64decode(dct["data"])
            return np.frombuffer(data, dtype=dct["dtype"]).reshape(dct["shape"])
        return dct

    return json.loads(json_str, object_hook=object_hook)


class NumpyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            if obj.dtype == np.float32:
                dtype = "float32"
            elif obj.dtype == np.float64:
                dtype = "float64"
            elif obj.dtype == np.int32:
                dtype = "int32"
            elif obj.dtype == np.int64:
                dtype = "int64"
            else:
                dtype = str(obj.dtype)

            return {"__numpy_array__": True, "data": base64.b64encode(obj.tobytes()).decode("ascii"), "dtype": dtype, "shape": obj.shape}
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)
