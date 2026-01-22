import os

SOURCE = 0
MIN_AREA = 500
DISPLAY = True
MIN_CONSECUTIVE = 3

LAT = 49.89
LONG = -97.13

FADE_DELAY = 0.5

MODEL_PATH = os.path.join("models", "face_recognizer.yml")
LABELS_PATH = os.path.join("models", "labels.json")
RECOGNITION_CONF_THRESHOLD = 30