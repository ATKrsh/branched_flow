"""
Frame extractor for reference video analysis.
Extracts frames at key timestamps for forensic analysis.
"""
import imageio.v3 as iio
import numpy as np
from pathlib import Path
from PIL import Image

VIDEO_PATH = r"E:\workspace\references\branched_flow.mp4"
OUT_DIR = Path(r"E:\workspace\branched_flow\analysis\frames")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Read video metadata
props = iio.improps(VIDEO_PATH, plugin="pyav")
print(f"Shape:    {props.shape}")
print(f"FPS:      {props.fps if hasattr(props, 'fps') else 'N/A'}")
print(f"Duration: {props.duration if hasattr(props, 'duration') else 'N/A'} sec")

# Count total frames by reading metadata
reader = iio.imopen(VIDEO_PATH, "r", plugin="pyav")
meta = reader.metadata()
print(f"Metadata: {meta}")

# Extract frames using pyav
frames_data = []
with iio.imopen(VIDEO_PATH, "r", plugin="pyav") as f:
    # Read every Nth frame
    for i, frame in enumerate(f.iter()):
        frames_data.append((i, frame))
        if i == 0:
            print(f"Frame 0 shape: {frame.shape}, dtype: {frame.dtype}")

total = len(frames_data)
fps = meta.get('fps', 30)
duration = total / fps
print(f"\nTotal frames: {total}")
print(f"FPS: {fps}")
print(f"Duration: {duration:.2f}s")

# Save strategic keyframes
# We want: first, 10%, 20%, 33%, 50%, 66%, 80%, 90%, last
targets = [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.33, 0.40,
           0.50, 0.60, 0.66, 0.75, 0.80, 0.90, 0.95, 0.99]

saved = []
for t in targets:
    idx = min(int(t * total), total - 1)
    frame_idx, frame = frames_data[idx]
    out_path = OUT_DIR / f"frame_{idx:05d}_t{t:.2f}.png"
    img = Image.fromarray(frame)
    img.save(out_path)
    saved.append(str(out_path))
    print(f"  Saved {out_path.name} ({frame.shape})")

print(f"\nExtracted {len(saved)} keyframes to {OUT_DIR}")
