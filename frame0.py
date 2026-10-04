"""Frame-0 priority for the dense WorldStereo -> WorldMirror V2 splat PLY.

The dense splats are written in per-view raster order (views x H x W). View 0 is the real input photo; views 1..N are
frames the video model generated, which disagree with each other and with view 0 in small ways (a face, for example).
Stacking all of them gives doubled features. This keeps all of view 0 and keeps a splat of a later view only where
view 0 has no surface of matching depth, so generated frames just fill what the photo cannot see.
"""
import os
import re
import time

import numpy as np

_PLY_DTYPES = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8", "uchar": "u1", "uint8": "u1",
               "char": "i1", "int8": "i1", "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2",
               "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4"}


def _read_ply(path):
    raw = open(path, "rb").read()
    marker = b"end_header\n"
    end = raw.index(marker) + len(marker)
    header = raw[:end].decode("latin1")
    if "format binary_little_endian" not in header:
        raise ValueError("only binary_little_endian PLY is supported")
    n = int(re.search(r"element vertex (\d+)", header).group(1))
    props = re.findall(r"property (\w+) (\w+)", header)
    dt = np.dtype([(name, _PLY_DTYPES[t]) for t, name in props])
    return header, np.frombuffer(raw[end:], dtype=dt, count=n).copy()


def infer_grid(n, views, frame_h, frame_w):
    """Find H, W with views*H*W == n whose aspect is closest to the frame aspect (WorldStereo's automatic 8% edge crop
    turns 576x320 frames into a 484x266 splat grid). None if there is no plausible grid."""
    if views < 1 or n % views:
        return None
    m = n // views
    aspect = frame_h / float(frame_w)
    centre = int((m / max(aspect, 1e-6)) ** 0.5)
    best = None
    for w in range(max(8, centre - 120), centre + 121):
        if m % w == 0:
            h = m // w
            err = abs(h / w - aspect)
            if best is None or err < best[0]:
                best = (err, h, w)
    if best is None or best[0] > 0.06:
        return None
    return best[1], best[2]


def frame0_priority(src_path, dst_path, views, frame_h, frame_w, tol=0.04):
    """Returns (kept, total), or None (and writes nothing) if the file does not have the expected layout."""
    header, a = _read_ply(src_path)
    n = len(a)
    grid = infer_grid(n, views, frame_h, frame_w)
    if grid is None:
        print(f"[HYW2Frame0Priority] cannot infer a {views}-view raster grid from {n} splats; passing through", flush=True)
        return None
    H, W = grid
    xyz = np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64).reshape(views, H, W, 3)
    flipped = np.median(xyz[..., 2]) < 0      # an already-flipped (x,-y,-z) file: undo it to get camera space
    cam = np.stack([xyz[..., 0], -xyz[..., 1], -xyz[..., 2]], -1) if flipped else xyz
    X, Y, Z = cam[0, ..., 0], cam[0, ..., 1], cam[0, ..., 2]
    if not (Z > 0).all():
        print("[HYW2Frame0Priority] view 0 has non-positive depth; passing through", flush=True)
        return None
    jj, ii = np.meshgrid(np.arange(W), np.arange(H))
    A = np.stack([jj.ravel(), np.ones(jj.size)], 1)
    px = np.linalg.lstsq(A, (X / Z).ravel(), rcond=None)[0]
    A2 = np.stack([ii.ravel(), np.ones(ii.size)], 1)
    py = np.linalg.lstsq(A2, (Y / Z).ravel(), rcond=None)[0]
    resid = float(np.abs((X / Z).ravel() - A @ px).mean())
    if resid > 0.08 or abs(px[0]) < 1e-9 or abs(py[0]) < 1e-9:
        print(f"[HYW2Frame0Priority] view 0 is not a clean identity pinhole (residual {resid:.3f}); passing through", flush=True)
        return None
    fx, cx = 1.0 / px[0], -px[1] / px[0]
    fy, cy = 1.0 / py[0], -py[1] / py[0]
    keep = np.ones((views, H, W), bool)
    for k in range(1, views):
        Xk, Yk, Zk = cam[k, ..., 0], cam[k, ..., 1], cam[k, ..., 2]
        ok = Zk > 1e-6
        safe = np.where(ok, Zk, 1.0)
        ui = np.rint(np.where(ok, fx * Xk / safe + cx, -1)).astype(int)
        vi = np.rint(np.where(ok, fy * Yk / safe + cy, -1)).astype(int)
        inside = ok & (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
        z0 = np.full(Zk.shape, np.inf)
        z0[inside] = Z[vi[inside], ui[inside]]
        keep[k] = ~(inside & (np.abs(Zk - z0) < tol * np.maximum(z0, 1e-6)))
    keep = keep.reshape(-1)
    new_header = re.sub(r"element vertex \d+", f"element vertex {int(keep.sum())}", header)
    with open(dst_path, "wb") as fh:
        fh.write(new_header.encode("latin1"))
        fh.write(a[keep].tobytes())
    return int(keep.sum()), n


class HYW2Frame0Priority:
    """Clean up the dense splat PLY: view 0 (the real photo) wins, later generated views only fill what it cannot see.
    Needs the same IMAGE batch that was fed to WorldMirror (for the view count and frame aspect). enable=0 or an
    unexpected layout passes the path through unchanged."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "path": ("STRING", {"forceInput": True}),
            "frames": ("IMAGE",),
            "tol": ("FLOAT", {"default": 0.04, "min": 0.005, "max": 0.3, "step": 0.005}),
            "enable": ("INT", {"default": 1, "min": 0, "max": 1}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "run"
    CATEGORY = "HYW2/io"

    def run(self, path, frames, tol, enable):
        if int(enable) == 0:
            return (path,)
        src = str(path)
        if not os.path.isfile(src):
            try:
                import folder_paths
                cand = os.path.join(folder_paths.get_output_directory(), src)
                if os.path.isfile(cand):
                    src = cand
            except Exception:
                pass
        views, fh_, fw_ = int(frames.shape[0]), int(frames.shape[1]), int(frames.shape[2])
        base, ext = os.path.splitext(src)
        dst = f"{base}_f0{ext or '.ply'}"
        t0 = time.time()
        res = frame0_priority(src, dst, views, fh_, fw_, float(tol))
        if res is None:
            return (path,)
        kept, total = res
        print(f"[HYW2Frame0Priority] kept {kept} of {total} splats ({100.0 * kept / total:.1f}%) -> {dst} "
              f"({time.time() - t0:.1f}s)", flush=True)
        return (dst,)
