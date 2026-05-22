# Dynamic Multi-Camera Engine

I have completely overhauled the AI Live Viewer to support **Dynamic Hot-Swappable Cameras**. You can now add an infinite number of cameras (Webcams or RTSP Streams) on-the-fly, while the AI is already running!

## Changes Made

1. **`app/storage/camera_manager.py`**:
   - Created a configuration manager to save all your cameras persistently to `data/config/cameras.json`. If you restart your laptop, all your cameras will automatically load and reconnect!

2. **`run_live_viewer.py`**:
   - Added a **Background CLI Listener Thread**. This thread waits for you to type `add` in the terminal and asks for your RTSP links without pausing or freezing the AI video feeds.
   - Made the multi-stream engine **thread-safe**. When you type the link, the engine instantly injects the new camera feed into the parallel AI processing loop.
   - A new OpenCV window will immediately pop open for the new camera, running full MOT tracking, GhostFaceNet recognition, and Evidence Logging.

## How to Test

1. Run the system: `.\.venv\Scripts\python run_live_viewer.py`
2. Wait for it to say `>>> AI Pipeline is LIVE! <<<`
3. Click on the terminal window and type `add`, then press Enter.
4. Follow the prompts to enter `1` for Webcam or `2` for an RTSP link.
5. Watch as the new camera window opens instantly while the old ones keep tracking seamlessly!
