import datetime
import random
import os
import json
import getpass
import math
import logging
import time
import threading
import tkinter as tk
import cv2
import speech_recognition as sr
import wmi
import pythoncom
from comtypes import cast, CLSCTX_ALL, POINTER
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import requests
import pywinstyles
from constants import (
    SOURCE,
    MIN_AREA,
    DISPLAY,
    MIN_CONSECUTIVE,
    LAT,
    LONG,
    FADE_DELAY,
    MODEL_PATH,
    LABELS_PATH,
    RECOGNITION_CONF_THRESHOLD,
    TIMEZONE,
    FACE_RECOGNITION_ENABLED
)


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class FadeData:
    """
    Class to hold fade state data.
    """
    faded_in = False

class TimeData:
    """
    Class to hold time display data.
    """
    OLD_TIME = ""

class Data:
    """
    Class to hold general data flags.
    """
    newData = False

EXPO_BACKOFF = 1000  # milliseconds

show_fullscreen_event = threading.Event()
show_withdraw_event = threading.Event()
stop = threading.Event()

root = tk.Tk()
width = root.winfo_screenwidth()
height = root.winfo_screenheight()
root.geometry(f"{width}x{height}")

# Source - https://stackoverflow.com/a/2745312
# Posted by msw
# Retrieved 2026-01-20, License - CC BY-SA 2.5
root.configure(background='black')

root.withdraw()

# print(# Source - https://stackoverflow.com/a/1594451
# # Posted by Marcin Augustyniak, modified by community. See post 'Timeline' for change history
# # Retrieved 2026-01-22, License - CC BY-SA 4.0

# getpass.getuser()()
# )

# this will eventually be used for news
# def get_api_value(key, default=None):
#     apifilename = "txt/api.txt"
#     try:
#         with open(apifilename, "r") as f:
#             for line in f:
#                 line = line.strip()
#                 if line.startswith(f"{key}:"):
#                     value = line.split(":", 1)[1].strip()
#                     # Try to convert to int if possible
#                     if value.isdigit():
#                         return int(value)
#                     try:
#                         return float(value)  # handles decimal numbers
#                     except ValueError:
#                         return value  # fallback to raw string
#     except FileNotFoundError:
#         logging.error(f"File {apifilename} not found")
#         return default
#     return default

def getWeather():
    def _fetch():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LAT,
            "longitude": LONG,
            "current_weather": True,
            "timezone": TIMEZONE
        }
        temp = None
        try:
            r = requests.get(url, params=params, timeout=5)
            print(r.url)
            r.raise_for_status()
            data = r.json()
            temp = data.get("current_weather", {}).get("temperature")
            if temp is None:
                logger.warning("getWeather: no temperature in response %s", data)
            else:
                logger.info("Temperature: %s", temp)
        except requests.RequestException as e:
            logger.error("getWeather network error: %s", e)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("getWeather parse error: %s", e)

        try:
            root.after(0, lambda: weather_var.set
                       (f"The temperature at {LAT}, {LONG} is \n {temp if temp is not None else 'N/A'}C°"))
        except tk.TclError as e:
            logger.debug("getWeather: failed to update tkinter variable: %s", e)

        try:
            root.after(60000, start_fetch_thread)
        except tk.TclError as e:
            logger.debug("getWeather: failed to schedule next fetch: %s", e)

    th = threading.Thread(target=_fetch, daemon=True)
    th.start()


def start_fetch_thread():
    return getWeather()

# i did this so that i can compare it below, it's only set once as a default
TimeData.OLD_TIME = str(datetime.datetime.now().replace(microsecond=0))[:-3]

def fadeInWindow():
    n = 0.01
    while n < 1.0:
        n += 0.01
        root.attributes('-alpha', n)
        root.update()
        time.sleep(FADE_DELAY)
    FadeData.faded_in = True

def fadeOutWindow():
    n = 1.0
    while n > 0.01:
        n -= 0.01
        root.attributes('-alpha', n)
        root.update()
        time.sleep(FADE_DELAY)
    FadeData.faded_in = False

def getTimeToDisplay():
    currentTime = str(datetime.datetime.now().strftime("%Y-%m-%d \n %H:%M:%S"))
    dayOfTheWeek = datetime.datetime.now().strftime("%A")
    dotwVar.set(dayOfTheWeek)
    timeVar.set(currentTime)
    if currentTime != TimeData.OLD_TIME:
        Data.newData = True
        TimeData.OLD_TIME = currentTime

def listen_for_ack():
    # CoInitialize COM for this thread (required by WMI/pywin32)
    try:
        pythoncom.CoInitialize()
    except pythoncom.error as e:
        logger.debug("pythoncom.CoInitialize: %s", e)
    try:
        try:
            devices = AudioUtilities.GetSpeakers()
            if hasattr(devices, "Activate"):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                volume = None
        except pythoncom.error as e:
            logger.debug("AudioUtilities.GetSpeakers failed: %s", e)
            volume = None

        try:
            c = wmi.WMI()
        except Exception as e:
            logger.debug("wmi.WMI() failed: %s", e)
            c = None

        try:
            t = wmi.WMI(moniker="//./root/wmi")
        except Exception as e:
            logger.debug("wmi WMI(moniker) failed: %s", e)
            t = None

        # Keep trying to open the microphone; if the stream closes, re-open and continue.
        while not stop.is_set():
            r = sr.Recognizer()
            # improve robustness in noisy environments
            r.dynamic_energy_threshold = True
            r.pause_threshold = 0.5

            try:
                with sr.Microphone() as source:
                    try:
                        r.adjust_for_ambient_noise(source, duration=1.0)
                    except (sr.UnknownValueError, sr.RequestError) as e:
                        logger.debug("adjust_for_ambient_noise failed: %s", e)

                    # Inner loop: listen until we hit a stream error, then break to re-open
                    while not stop.is_set():
                        try:
                            logger.info("listening...")
                            audio = r.listen(source, timeout=None, phrase_time_limit=5)
                            try:
                                text = r.recognize_google(audio).lower()
                            except sr.UnknownValueError:
                                continue
                            except sr.RequestError as e:
                                logger.error("Speech recognition request failed: %s", e)
                                time.sleep(1)
                                continue

                            logger.info("Recognized text: %s", text)
                            # accept several common variants/short forms
                            if any(k in text for k in ("acknowledge", "acknowledged", "i acknowledge", "ack")):
                                show_withdraw_event.set()
                                Data.newData = False
                        except (OSError, IOError, sr.WaitTimeoutError) as e:
                            # Stream closed or I/O error. break to outer loop and re-open microphone
                            logger.warning("listen error (stream closed or I/O): %s", e)
                            break
            except (OSError, IOError, sr.RequestError) as e:
                logger.error("microphone error (opening): %s", e)

            # small delay before retrying to open microphone
            time.sleep(1)
    finally:
        pythoncom.CoUninitialize()

def open_cv_main():
    # open video source
    try:
        src = int(SOURCE)
    except (ValueError, TypeError):
        logger.warning("SOURCE is not an integer. Defaulting to 0. ")
        src = 0
    cap = cv2.VideoCapture(src)

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    except Exception as e:
        pass
    if not cap.isOpened():
        logger.error("Cannot open video source: %s", SOURCE)
        time.sleep(EXPO_BACKOFF / 1000.0)
        EXPO_BACKOFF += 1000
        EXPO_BACKOFF = min(EXPO_BACKOFF * 2, 16000)  # cap backoff at 16 seconds
        if EXPO_BACKOFF == 16000:
            logger.info("Max backoff reached. Stopping. ")
            stop.set()
            root.after(0, root.quit)
            return

    background = None
    alpha = 0.02
    consec_frames = 0
    # small kernel for morphological opening to remove speckle noise
    morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    logger.info("Starting motion detection. Press 'q' in the window to quit.")
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    # eye cascade used for simple alignment
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    recognizer = None
    labels = {}
    # initial load only if opt-in enabled
    try:
        if FACE_RECOGNITION_ENABLED:
            if hasattr(cv2, 'face') and os.path.exists(MODEL_PATH):
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                recognizer.read(MODEL_PATH)
                logger.info('Loaded face recognizer model from %s', MODEL_PATH)
            elif hasattr(cv2, 'face') and not os.path.exists(MODEL_PATH):
                logger.warning('Face recognizer model not found at %s', MODEL_PATH)
            else:
                logger.warning('cv2.face module not available; skipping face recognition')
    except Exception as e:
        logger.error('Error loading recognizer: %s', e)

    try:
        if os.path.exists(LABELS_PATH):
            with open(LABELS_PATH, 'r', encoding='utf-8') as f:
                labels = json.load(f)
                # labels expected as {"1": "Alice", "2": "Bob"}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Failed to load labels: %s", e)
        labels = {}

    open_cv_main.last_seen = None
    open_cv_main.last_seen_time = 0
    try:
        while not stop.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            # face detection/recognition
            try:
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            except Exception as e:
                logger.debug("face_cascade.detectMultiScale failed: %s", e)
                faces = ()

            # dynamically load/unload recognizer based on runtime opt-in
            if FACE_RECOGNITION_ENABLED and recognizer is None:
                try:
                    if hasattr(cv2, 'face') and os.path.exists(MODEL_PATH):
                        recognizer = cv2.face.LBPHFaceRecognizer_create()
                        recognizer.read(MODEL_PATH)
                        logger.info('Loaded face recognizer at runtime from %s', MODEL_PATH)
                except Exception as e:
                    logger.error('Error loading recognizer at runtime: %s', e)
            elif not FACE_RECOGNITION_ENABLED and recognizer is not None:
                recognizer = None
                logger.info('Unloaded face recognizer at runtime')

            for (fx, fy, fw, fh) in faces:
                try:
                    face_roi = gray[fy:fy+fh, fx:fx+fw]
                    # align face to reduce effect of roll/tilt
                    def align_face(face_gray):
                        try:
                            eyes = eye_cascade.detectMultiScale(face_gray, scaleFactor=1.1, minNeighbors=5, minSize=(15, 15))
                            if len(eyes) >= 2:
                                # pick two eyes sorted by x coordinate
                                eyes_sorted = sorted(eyes, key=lambda e: e[0])[:2]
                                (ex1, ey1, ew1, eh1) = eyes_sorted[0]
                                (ex2, ey2, ew2, eh2) = eyes_sorted[1]
                                c1 = (ex1 + ew1/2.0, ey1 + eh1/2.0)
                                c2 = (ex2 + ew2/2.0, ey2 + eh2/2.0)
                                dx = c2[0] - c1[0]
                                dy = c2[1] - c1[1]
                                if dx == 0:
                                    return face_gray
                                angle = math.degrees(math.atan2(dy, dx))
                                # rotate around center of face
                                (h, w) = face_gray.shape[:2]
                                center = (w // 2, h // 2)
                                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                                rotated = cv2.warpAffine(face_gray, M, (w, h), flags=cv2.INTER_LINEAR)
                                return rotated
                        except Exception:
                            pass
                        return face_gray

                    aligned = align_face(face_roi)
                    face_resized = cv2.resize(aligned, (200, 200))
                except Exception as e:
                    logger.debug("face resize failed: %s", e)
                    continue

                if recognizer is not None:
                    try:
                        label_id, confidence = recognizer.predict(face_resized)
                        # logger.info('predict -> id=%s conf=%s', label_id, confidence)
                    except Exception as e:
                        logger.debug("recognizer.predict failed: %s", e)
                        label_id, confidence = None, None

                    name = labels.get(str(label_id)) if label_id is not None else None

                    if name and confidence is not None and confidence < RECOGNITION_CONF_THRESHOLD:
                        display_conf = int(confidence)
                        cv2.putText(frame, f"{name} ({display_conf})", (fx, fy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)
                        cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (0, 255, 0), 2)
                        now = time.time()
                        if open_cv_main.last_seen != name or (now - open_cv_main.last_seen_time) > 5:
                            open_cv_main.last_seen = name
                            open_cv_main.last_seen_time = now
                            try:
                                root.after(0, lambda n=name: userVar.set(f"Welcome, {n}"))
                            except tk.TclError as e:
                                logger.debug("failed to update userVar: %s", e)
                            # show_fullscreen_event.set()
                    else:
                        cv2.putText(frame, "Unknown", (fx, fy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                        userVar.set(f"Welcome, {getpass.getuser()} (logged on user)")
                        cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (0, 0, 255), 2)

            if background is None:
                background = gray.astype("float")
                if DISPLAY:
                    cv2.imshow("Motion", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                continue

            cv2.accumulateWeighted(gray, background, alpha)
            frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(background))
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            # remove small speckles then dilate to join nearby regions
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, morph_kernel, iterations=1)
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            boxes = []
            for c in contours:
                if cv2.contourArea(c) < MIN_AREA:
                    continue
                (x, y, w, h) = cv2.boundingRect(c)
                boxes.append((x, y, w, h))

            motion = len(boxes) > 0
            if motion:
                consec_frames += 1
            else:
                consec_frames = max(0, consec_frames - 1)

            # only show boxes when motion has been persistent for several frames
            if consec_frames >= MIN_CONSECUTIVE:
                for (x, y, w, h) in boxes:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if DISPLAY:
                cv2.imshow("Motion", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                time.sleep(0.01)

            # track consecutive frames with no motion and request fullscreen
            if not motion:
                consec_no_motion = getattr(open_cv_main, "consec_no_motion", 0) + 1
                open_cv_main.consec_no_motion = consec_no_motion
            else:
                open_cv_main.consec_no_motion = 0

            if getattr(open_cv_main, "consec_no_motion", 0) >= 200:
                if not show_fullscreen_event.is_set():
                    logger.info("No motion - requesting fullscreen")
                    show_fullscreen_event.set()
                    open_cv_main.consec_no_motion = 0

            getTimeToDisplay()

            # if getattr(open_cv_main, "consec_no_motion", 0) <= 200:
            #     if not show_withdraw_event.is_set():
            #         print("Not at threshold - withdrawing")
            #         show_withdraw_event.set()
    finally:
        stop.set()
        cap.release()
        if DISPLAY:
            cv2.destroyAllWindows()

def _poll_fullscreen():
    if show_fullscreen_event.is_set() and Data.newData:
        try:
            root.deiconify()
            root.attributes("-fullscreen", True)
            root.lift()
            root.focus_force()
            if not FadeData.faded_in:
                fadeInWindow()
        except Exception:
            pass
        show_fullscreen_event.clear()
        Data.newData = False
    root.after(200, _poll_fullscreen)

def _poll_withdraw():
    if show_withdraw_event.is_set():
        try:
            fadeOutWindow()
            root.withdraw()
        except Exception:
            pass
        show_withdraw_event.clear()
    root.after(200, _poll_withdraw)

#     # Source - https://stackoverflow.com/a/77850151
#     # Posted by Akascape, modified by community. See post 'Timeline' for change history
#     # Retrieved 2026-01-21, License - CC BY-SA 4.0

def increaseOpacityFrame(frame0):
    """Increases the opacity of the given frame."""
    n = 0.01
    while n < 1.0:
        n += 0.01
        pywinstyles.set_opacity(frame0, n, color=None)
        root.update()
        time.sleep(FADE_DELAY)

def decreaseOpacityFrame(frame0):
    """Decreases the opacity of the given frame."""
    n = 1.0
    while n > 0.01:
        n -= 0.01
        pywinstyles.set_opacity(frame0, n, color=None)
        root.update()
        time.sleep(FADE_DELAY)

def moveFrame0(frame0):
    frame0.update_idletasks()
    frame_width = frame0.winfo_width()
    frame_height = frame0.winfo_height()

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    max_x = max(0, screen_width - frame_width)
    max_y = max(0, screen_height - frame_height)

    new_x = random.randint(0, max_x)
    new_y = random.randint(0, max_y)
    decreaseOpacityFrame(frame0)

    frame0.place_forget()
    frame0.place(x=new_x, y=new_y)

    increaseOpacityFrame(frame0)
    root.after(35000, lambda: moveFrame0(frame0))

Frame0 = tk.Frame(root)
Frame0.configure(bg="black")
Frame0.place(x=0, y=0)

root.after(35000, lambda: moveFrame0(Frame0))

timeVar = tk.StringVar(value="time")
timeLabel = tk.Label(Frame0, textvariable=timeVar, fg='white', bg='black', font=('Helvetica', 60))
timeLabel.pack(expand=True)

dotwVar = tk.StringVar(value="dotw")
dotwLabel = tk.Label(Frame0, textvariable=dotwVar, fg='white', bg='black', font=('Helvetica', 60))
dotwLabel.pack(expand=True)

weather_var = tk.StringVar(value="weather")
weatherLabel = tk.Label(Frame0, textvariable=weather_var, fg='white', bg='black', font=('Helvetica', 60))
weatherLabel.pack(expand=True)

userVar = tk.StringVar(value=f"Welcome, {getpass.getuser()} (logged on user)")
userLabel = tk.Label(Frame0, textvariable=userVar, fg='white', bg='black', font=('Helvetica', 60))
userLabel.pack(expand=True)

if __name__ == '__main__':
    root.after(200, _poll_fullscreen)
    root.after(200, _poll_withdraw)
    captureThread = threading.Thread(target=open_cv_main, daemon=True)
    listenThread = threading.Thread(target=listen_for_ack, daemon=True)
    captureThread.start()
    listenThread.start()

    start_fetch_thread()

    def _on_close():
        stop.set()
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", _on_close)
    try:
        root.mainloop()
    finally:
        stop.set()
        try:
            captureThread.join(timeout=2)
        except Exception:
            logging.error("Error joining captureThread", exc_info=True)
        try:
            listenThread.join(timeout=2)
        except Exception:
            logging.error("Error joining listenThread", exc_info=True)
        stop.set()
        root.after(0, root.quit)