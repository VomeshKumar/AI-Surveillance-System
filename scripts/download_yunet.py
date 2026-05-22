import urllib.request
import os

# YuNet 2023mar version from OpenCV Zoo
url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
output_dir = "D:/ai-surveillance-engine/artifacts"
output_path = os.path.join(output_dir, "yunet.onnx")

os.makedirs(output_dir, exist_ok=True)

print(f"Downloading YuNet to {output_path}...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
        data = response.read()
        out_file.write(data)
    print("YuNet Download completed successfully!")
except Exception as e:
    print(f"YuNet Download failed: {e}")
