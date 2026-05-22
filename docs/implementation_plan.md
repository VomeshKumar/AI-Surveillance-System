# Dynamic Hot-Swappable Camera Engine

We need to allow the user to add new cameras (Webcam or RTSP) dynamically *while* the AI surveillance pipeline is actively running, without pausing the video streams or dropping frames.

## User Review Required

- **Terminal Interaction**: I will add a background thread that constantly listens to your terminal. While the video windows are running, you can simply type `add` in the terminal and press Enter. It will then prompt you for the RTSP link or Webcam index, and instantly pop open a new window processing that feed!
- **Database Persistence**: Do you want these newly added cameras to be saved permanently so they automatically open next time you run the script? (I will implement this using a simple config file `data/config/cameras.json`).

## Proposed Changes

### 1. `run_live_viewer.py`
- **[MODIFY]** Implement a `CLI_Listener` background thread. This thread will use `input()` to ask for camera details without blocking the `cv2.imshow()` loop.
- **[MODIFY]** Make the `cameras` list thread-safe so the CLI thread can inject new `CameraStream` objects directly into the live AI loop.
- **[MODIFY]** Add a `data/config/cameras.json` loader. On startup, the system will load all previously saved cameras. When a new camera is added dynamically, it gets saved to this file.

### 2. `app/storage/camera_manager.py`
- **[NEW]** Create a simple JSON-based configuration manager to load and save camera states persistently.

## Verification Plan

1. Start `run_live_viewer.py`. It will load any default cameras.
2. While the camera is running and AI tracking is active, type `add` in the terminal.
3. Answer the prompts (e.g., `2` for RTSP, enter the link).
4. Verify that a new OpenCV window instantly opens and begins running YuNet, GhostFaceNet, MOT, and Evidence Logging on the new stream!
