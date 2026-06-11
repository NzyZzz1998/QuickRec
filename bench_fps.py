"""帧率基准测试：测量单帧捕获+编码耗时"""
import time
import cv2
import numpy as np
from mss import MSS

fps = 60
frame_interval = 1.0 / fps

with MSS() as sct:
    monitor = sct.monitors[1]
    size = (monitor["width"], monitor["height"])
    writer = cv2.VideoWriter("_bench.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, size)

    # 预热
    for _ in range(5):
        img = np.array(sct.grab(monitor), dtype=np.uint8)[:, :, :3]
        writer.write(img)

    # 正式测量
    capture_times = []
    write_times = []
    total_times = []

    for i in range(300):  # 5秒 @ 60fps
        t0 = time.perf_counter()
        img = np.array(sct.grab(monitor), dtype=np.uint8)[:, :, :3]
        t1 = time.perf_counter()
        writer.write(img)
        t2 = time.perf_counter()

        capture_times.append((t1 - t0) * 1000)
        write_times.append((t2 - t1) * 1000)
        total_times.append((t2 - t0) * 1000)

        # 模拟帧率控制
        wait = frame_interval - (t2 - t0)
        if wait > 0:
            time.sleep(wait)

    writer.release()

    print(f"=== 帧率基准测试 ({fps}fps 目标) ===")
    print(f"捕获(mss.grab):  avg={np.mean(capture_times):.1f}ms  max={np.max(capture_times):.1f}ms  min={np.min(capture_times):.1f}ms")
    print(f"编码(cv2.write):  avg={np.mean(write_times):.1f}ms  max={np.max(write_times):.1f}ms  min={np.min(write_times):.1f}ms")
    print(f"总耗时:           avg={np.mean(total_times):.1f}ms  max={np.max(total_times):.1f}ms  min={np.min(total_times):.1f}ms")
    print(f"帧间隔:           {frame_interval*1000:.1f}ms")
    overhead = np.mean(total_times) - frame_interval * 1000
    print(f"预估可达帧率:     {1000/np.mean(total_times):.0f}fps")
    if overhead > 0:
        print(f"⚠ 每帧超出帧间隔 {overhead:.1f}ms，无法达到 {fps}fps")
    else:
        print(f"✓ 每帧余量 {-overhead:.1f}ms，可达 {fps}fps")

import os
os.remove("_bench.mp4")