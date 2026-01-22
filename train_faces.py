import os
import cv2
import json
import argparse
import numpy as np


def build_and_train(dataset_dir, model_path, labels_path):
    if not hasattr(cv2, 'face'):
        print('cv2.face not available. Install opencv-contrib-python and retry.')
        return 2

    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

    faces = []
    labels = []
    label_ids = {}
    next_id = 0

    for person in sorted(os.listdir(dataset_dir)) if os.path.exists(dataset_dir) else []:
        person_dir = os.path.join(dataset_dir, person)
        if not os.path.isdir(person_dir):
            continue
        if person not in label_ids:
            label_ids[person] = next_id
            next_id += 1
        for fn in sorted(os.listdir(person_dir)):
            if not fn.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            path = os.path.join(person_dir, fn)
            img = cv2.imread(path)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rects = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(rects) == 0:
                continue
            x, y, w, h = rects[0]
            roi = gray[y:y+h, x:x+w]
            try:
                roi_resized = cv2.resize(roi, (200, 200))
            except Exception:
                continue
            faces.append(roi_resized)
            labels.append(label_ids[person])

    if not faces:
        print('No faces found in dataset. Prepare `dataset/<person>/<images>` and try again.')
        return 1

    faces_np = np.array(faces)
    labels_np = np.array(labels)

    os.makedirs(os.path.dirname(model_path) or '.', exist_ok=True)
    os.makedirs(os.path.dirname(labels_path) or '.', exist_ok=True)

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces_np, labels_np)
    recognizer.write(model_path)

    # invert label_ids for human-readable mapping in JSON
    inv = {v: k for k, v in label_ids.items()}
    with open(labels_path, 'w', encoding='utf-8') as f:
        json.dump(inv, f, ensure_ascii=False)

    print(f'Wrote model to {model_path}')
    print(f'Wrote labels to {labels_path}')
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Train LBPH face recognizer from a dataset folder.')
    p.add_argument('--dataset', default='dataset', help='Dataset root: dataset/<person>/*.jpg')
    p.add_argument('--model', default=os.path.join('models', 'face_recognizer.yml'), help='Output model path')
    p.add_argument('--labels', default=os.path.join('models', 'labels.json'), help='Output labels JSON')
    args = p.parse_args()
    rc = build_and_train(args.dataset, args.model, args.labels)
    raise SystemExit(rc)
