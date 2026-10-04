# ComfyUI-HYWorld2Glue

Small glue nodes for the HY-World 2.0 Graydient workflows built on
[AHEKOT/ComfyUI_HYWorld2](https://github.com/AHEKOT/ComfyUI_HYWorld2).

| Node | What it does |
|---|---|
| `HYW2 Stopwatch (IMAGE / STRING / PLY_DATA / WORLDSTEREO_MODEL / WORLDMIRROR_MODEL)` | Typed pass-through. Prints `[HYW2 STOPWATCH] <label>: N s since ComfyUI process start \| +M s since previous mark`. "Since process start" is the clock Graydient's ~180 s run-time limit appears to use. |
| `HYW2 Stopwatch (STRING, output)` | Same, but an OUTPUT_NODE, so it can terminate a chain nothing else consumes. |
| `HYW2 Flip PLY upright` | `flip=1` rotates a saved 3D-Gaussian-splat PLY 180 deg about X (positions, normals and each Gaussian's quaternion) so OpenCV camera-space scenes (y down) open upright in y-up viewers. `flip=0` passes the path through. |
| `HYW2 Frame-0 priority (dedupe later views)` | For the dense WorldStereo -> WorldMirror V2 splat PLY (rows in per-view raster order, views x H x W). Keeps every splat of view 0 (the real photo) and keeps a splat of a later generated view only where view 0 has no surface of matching depth (|dz| < `tol` x depth, default 4%), so generated frames only fill what the photo cannot see instead of stacking a second, slightly different surface (doubled lips/teeth). Needs the IMAGE batch fed to WorldMirror (view count + frame aspect). Fits view 0's pinhole from its own grid and assumes camera 0 is the identity. Passes the path through unchanged if the layout is unexpected or `enable=0`. On the pirate test scene it kept 28% of 901,208 splats (commanded poses) in 0.4 s. |

Typed pass-throughs are used instead of a `*` wildcard on purpose: ComfyUI's link-type validation of custom wildcards
has changed between versions.
