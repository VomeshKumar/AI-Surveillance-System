import urllib.request
import os

url = "https://raw.githubusercontent.com/andestech/ModelZoo/master/ModelZoo/GhostFaceNet/Model/ghostface_fp32.onnx"
output_path = "D:/ai-surveillance-engine/artifacts/ghostfacenet.onnx"

print(f"Downloading GhostFaceNet to {output_path}...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
        data = response.read()
        out_file.write(data)
    print("Download completed successfully!")
except Exception as e:
    print(f"Download failed: {e}")
