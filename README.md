
# ambientComputing

Make an idle computer feel more inviting and personal by showing time, weather, and a personalized greeting.

Overview

- Purpose: When the system is idle, show a fullscreen info screen (time, day, weather, and optional personal greeting).
- Triggering: motion detection via webcam triggers/controls behavior; saying "acknowledge" (speech) will dismiss the screen.
- Personalization: optional local face recognition (LBPH) to greet known users.

Quick start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. (Optional) Train the face model from `dataset/<person>/*.jpg` using the included trainer:

```bash
python train_faces.py --dataset dataset --model models/face_recognizer.yml --labels models/labels.json
```

3. Configure `constants.py` (camera source, thresholds, model paths, whether to enable face recognition, lat/long for weather).

4. Run the app:

```bash
python main.py
```

Files of interest

- `main.py`: main application (motion detection, face recognition, UI, speech listen).
- `train.txt`: command to train face recognition model with default paths.
- `train_faces.py`: prepares dataset and trains an LBPH model; writes model and `labels.json`.
- `constants.py`: runtime configuration (paths, thresholds, time zone, coordinates).

Face recognition notes

- The trainer and recognizer use OpenCV's LBPH (`cv2.face.LBPHFaceRecognizer`). This is CPU-only; it will not automatically use a GPU.
- To improve accuracy use many clear face images per person, consistent lighting and frontal faces.
- `train_faces.py` writes `models/face_recognizer.yml` and `models/labels.json`. `main.py` loads those when `FACE_RECOGNITION_ENABLED` is true.
The files to train with must be .png, .jpg, or .jpeg file types.

GPU and performance

- The current implementation is CPU-bound. OpenCV can be built with CUDA support, but LBPH has no standard CUDA implementation. To use GPU training/inference, migrate to a deep-learning pipeline (PyTorch/TensorFlow) and use GPU-accelerated models.

Privacy and networking

- Face recognition is local (model/data stored locally).
- Some features use web APIs (e.g., weather); see `main.py` for endpoints used.

Troubleshooting

- If face recognition never identifies anyone:
- Confirm `models/face_recognizer.yml` and `models/labels.json` exist and paths in `constants.py` are correct.
- Run `train_faces.py` with a properly structured `dataset/` folder.
- Add debug prints to `main.py` around `recognizer.predict()` to see `label_id` and `confidence`.
- If the webcam cannot be opened, check `SOURCE` in `constants.py` and that no other app is using the camera.

Warnings

- This software interacts with hardware (camera, microphone), uses online APIs, and can block the desktop with a fullscreen window. Use carefully.
- The author disclaims responsibility for system crashes or unexpected behavior.

Contributing

- Clean, focused PRs are welcome. If adding GPU-capable training/recognition, include a README section explaining dependencies and migration steps.
