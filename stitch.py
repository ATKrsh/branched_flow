import cv2
import os

input_dir = "preview_frames"
output_file = "preview_video.mp4"
fps = 60

# get frames
frames = [f for f in os.listdir(input_dir) if f.endswith(".png")]
frames.sort()

if not frames:
    print("No frames found!")
    exit(1)

# read first frame to get dims
first_frame = cv2.imread(os.path.join(input_dir, frames[0]))
height, width, layers = first_frame.shape

fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
video = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

print(f"Stitching {len(frames)} frames into {output_file}...")

for f in frames:
    video.write(cv2.imread(os.path.join(input_dir, f)))

cv2.destroyAllWindows()
video.release()
print("Video saved successfully!")
