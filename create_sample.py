import cv2
import numpy as np

width, height = 640, 360
fps = 30
duration = 2
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('sample.mp4', fourcc, fps, (width, height))

for i in range(fps * duration):
    # Make a frame that changes color over time to avoid being empty
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    color_val = int((i / (fps * duration)) * 255)
    frame[:] = (color_val, 100, 200)
    
    # Draw a moving square
    x = int((i / (fps * duration)) * width)
    cv2.rectangle(frame, (x, 100), (x+50, 150), (255, 255, 255), -1)
    
    out.write(frame)

out.release()
print("sample.mp4 created successfully")
