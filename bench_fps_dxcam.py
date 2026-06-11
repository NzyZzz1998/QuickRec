"""dxcam 帧率基准测试"""
import time
import cv2
import numpy as np
import dxcam

fps = 60
frame_interval = 1.0 / fps

cam = dxcam.create(output_idx=0, output_color="BGR")
cam.start(target_fps=60)
time.sleep(0.1)  # 等待 dxcam 线程启动

frame0 = cam.get_latest_frame()
while frame0 is None:
    time.sleep(0.01)
    frame0 = cam.get_latest_frame()
size = (frame0.shape[1], frame0.shape[0])
writer = cv2.VideoWriter("_bench_dxcam.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, size)

capture_times = []
write_times = []
total_times = []

for i in range(300):
    t0 = time.perf_counter()
    frame = cam.get_latest_frame()
    t1 = time.perf_counter()
    if frame is not None:
        writer.write(frame)
    t2 = time.perf_counter()

    capture_times.append((t1 - t0) * 1000)
    write_times.append((t2 - t1) * 1000)
    total_times.append((t2 - t0) * 1000)

    wait = frame_interval - (t2 - t0)
    if wait > 0.001:
        time.sleep(wait - 0.001)
    while time.time() < t0 + frame_interval:
        pass

cam.stop()
cam.release()
writer.release()

print(f"=== dxcam 帧率基准测试 ({fps}fps 目标) ===")
print(f"capture(get_latest_frame): avg={np.mean(capture_times):.2f}ms  max={np.max(capture_times):.2f}ms")
print(f"encode(cv2.write):       avg={np.mean(write_times):.2f}ms  max={np.max(write_times):.2f}ms")
print(f"total:                   avg={np.mean(total_times):.2f}ms  max={np.max(total_times):.2f}ms")
print(f"frame_interval:          {frame_interval*1000:.2f}ms")
overhead = np.mean(total_times) - frame_interval * 1000
print(f"estimated_fps:           {1000/np.mean(total_times):.0f}fps")
if overhead > 0:
    print(f"WARN: each frame exceeds interval by {overhead:.1f}ms")
else:
    print(f"OK: each frame has {-overhead:.1f}ms margin")

import os
os.remove("_bench_dxcam.mp4")