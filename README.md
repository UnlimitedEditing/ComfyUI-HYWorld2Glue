# ComfyUI-HYWorld2Glue

Small glue nodes for the HY-World 2.0 Graydient workflows built on
[AHEKOT/ComfyUI_HYWorld2](https://github.com/AHEKOT/ComfyUI_HYWorld2).

| Node | What it does |
|---|---|
| `HYW2 Stopwatch (IMAGE / STRING / PLY_DATA / WORLDSTEREO_MODEL / WORLDMIRROR_MODEL)` | Typed pass-through. Prints `[HYW2 STOPWATCH] <label>: N s since ComfyUI process start \| +M s since previous mark`. "Since process start" is the clock Graydient's ~180 s run-time limit appears to use. |
| `HYW2 Stopwatch (STRING, output)` | Same, but an OUTPUT_NODE, so it can terminate a chain nothing else consumes. |
| `HYW2 Flip PLY upright` | `flip=1` rotates a saved 3D-Gaussian-splat PLY 180 deg about X (positions, normals and each Gaussian's quaternion) so OpenCV camera-space scenes (y down) open upright in y-up viewers. `flip=0` passes the path through. |

Typed pass-throughs are used instead of a `*` wildcard on purpose: ComfyUI's link-type validation of custom wildcards
has changed between versions.
