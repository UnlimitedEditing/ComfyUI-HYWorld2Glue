import os
import re
import time

import numpy as np

_IMPORT_T = time.time()
_LAST = {"t": None}


def _since_process_start() -> float:
    """Seconds since this ComfyUI process started (falls back to module import time)."""
    try:
        import psutil
        return time.time() - psutil.Process(os.getpid()).create_time()
    except Exception:
        return time.time() - _IMPORT_T


def _mark(label: str) -> None:
    now = time.time()
    delta = 0.0 if _LAST["t"] is None else now - _LAST["t"]
    _LAST["t"] = now
    print(f"[HYW2 STOPWATCH] {label}: {_since_process_start():7.1f}s since ComfyUI process start | +{delta:6.1f}s since previous mark", flush=True)


def _make_stopwatch(type_name: str, class_suffix: str, output_node: bool = False):
    """One typed pass-through class per socket type (a '*' wildcard is avoided on purpose: ComfyUI's
    link-type validation of custom wildcards has changed between versions)."""

    class _StopWatch:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {
                "value": (type_name, {"forceInput": True}),
                "label": ("STRING", {"default": "mark"}),
            }}

        RETURN_TYPES = (type_name,)
        RETURN_NAMES = ("value",)
        FUNCTION = "mark"
        CATEGORY = "HYW2/timing"
        OUTPUT_NODE = output_node

        def mark(self, value, label):
            _mark(label)
            return (value,)

    _StopWatch.__name__ = f"HYW2StopWatch{class_suffix}"
    return _StopWatch


_TYPES = {
    "Image": "IMAGE",
    "String": "STRING",
    "PlyData": "PLY_DATA",
    "WorldStereoModel": "WORLDSTEREO_MODEL",
    "WorldMirrorModel": "WORLDMIRROR_MODEL",
}
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
for _suffix, _t in _TYPES.items():
    _cls = _make_stopwatch(_t, _suffix)
    NODE_CLASS_MAPPINGS[_cls.__name__] = _cls
    NODE_DISPLAY_NAME_MAPPINGS[_cls.__name__] = f"HYW2 Stopwatch ({_t})"
# terminal variant: an OUTPUT_NODE so it executes even though nothing consumes it
_end = _make_stopwatch("STRING", "StringEnd", output_node=True)
NODE_CLASS_MAPPINGS[_end.__name__] = _end
NODE_DISPLAY_NAME_MAPPINGS[_end.__name__] = "HYW2 Stopwatch (STRING, output)"

_PLY_DTYPES = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8", "uchar": "u1", "uint8": "u1",
               "char": "i1", "int8": "i1", "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2",
               "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4"}


def flip_ply_upright(src_path: str, dst_path: str) -> int:
    """Rotate a binary 3DGS PLY by 180 deg about X: (x,y,z)->(x,-y,-z), normals likewise, and left-multiply every
    Gaussian's orientation quaternion (rot_0..3 = w,x,y,z) by (0,1,0,0), i.e. (w,x,y,z)->(-x,w,-z,y).
    Returns the number of vertices written."""
    raw = open(src_path, "rb").read()
    marker = b"end_header\n"
    end = raw.index(marker) + len(marker)
    header = raw[:end].decode("latin1")
    if "format binary_little_endian" not in header:
        raise ValueError("only binary_little_endian PLY is supported")
    n = int(re.search(r"element vertex (\d+)", header).group(1))
    props = re.findall(r"property (\w+) (\w+)", header)
    dt = np.dtype([(name, _PLY_DTYPES[t]) for t, name in props])
    a = np.frombuffer(raw[end:], dtype=dt, count=n).copy()
    names = set(dt.names)
    if not {"x", "y", "z"} <= names:
        raise ValueError("PLY has no x/y/z properties")
    a["y"] = -a["y"]
    a["z"] = -a["z"]
    if {"ny", "nz"} <= names:
        a["ny"] = -a["ny"]
        a["nz"] = -a["nz"]
    if {"rot_0", "rot_1", "rot_2", "rot_3"} <= names:
        w, x, y, z = (a[k].copy() for k in ("rot_0", "rot_1", "rot_2", "rot_3"))
        a["rot_0"], a["rot_1"], a["rot_2"], a["rot_3"] = -x, w, -z, y
    with open(dst_path, "wb") as fh:
        fh.write(raw[:end])
        fh.write(a.tobytes())
    return n


class HYW2FlipPLY:
    """HY-World / WorldMirror PLYs are in OpenCV camera coordinates (y down). Most splat viewers assume y-up and show
    the scene upside down. flip=1 writes <name>_upright.ply next to the input and returns its path; flip=0 passes the
    path through unchanged."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "path": ("STRING", {"forceInput": True}),
            "flip": ("INT", {"default": 1, "min": 0, "max": 1}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "run"
    CATEGORY = "HYW2/io"

    def run(self, path, flip):
        if int(flip) == 0:
            return (path,)
        src = str(path)
        if not os.path.isfile(src):
            # SavePLY may return a path relative to ComfyUI's output dir
            try:
                import folder_paths
                cand = os.path.join(folder_paths.get_output_directory(), src)
                if os.path.isfile(cand):
                    src = cand
            except Exception:
                pass
        base, ext = os.path.splitext(src)
        dst = f"{base}_upright{ext or '.ply'}"
        t0 = time.time()
        n = flip_ply_upright(src, dst)
        print(f"[HYW2FlipPLY] {n} splats -> {dst} ({time.time() - t0:.1f}s)", flush=True)
        return (dst,)


NODE_CLASS_MAPPINGS["HYW2FlipPLY"] = HYW2FlipPLY
NODE_DISPLAY_NAME_MAPPINGS["HYW2FlipPLY"] = "HYW2 Flip PLY upright"
