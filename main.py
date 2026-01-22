# style: no comments, self-explanatory code

try:
    import time
    import threading
    import tkinter as tk
    import cv2
    import speech_recognition as sr
    import wmi
    import pythoncom
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    import sys
    import datetime
    import requests
    import random
    import pywinstyles
    import os
    import json
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
        TIMEZONE
    )
except ImportError as e:
    print(f"You're missing a package. Install with pip. {e}")

global fadedIn

fadedIn = False

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

class Data:
    newData = False

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

def getWeather(weatherVar):
    def _fetch():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LAT,
            "longitude": LONG,
            "current_weather": True,
            "timezone": TIMEZONE,
        }
        temp = None
        try:
            r = requests.get(url, params=params, timeout=5)
            r.raise_for_status()
            data = r.json()
            temp = data.get("current_weather", {}).get("temperature")
            if temp is None:
                print("getWeather: no temperature in response", data)
            else:
                print(temp)
        except Exception as e:
            print("getWeather error:", e)

        try:
            root.after(0, lambda: weatherVar.set
                       (f"The temperature at {LAT}, {LONG} is \n {temp if temp is not None else 'N/A'}C°"))
        except Exception:
            pass

        try:
            root.after(60000, start_fetch_thread)
        except Exception:
            pass

    th = threading.Thread(target=_fetch, daemon=True)
    th.start()


def start_fetch_thread():
    return getWeather(weatherVar)

# i did this so that i can compare it below, it's only set once as a default
oldTime = str(datetime.datetime.now().replace(microsecond=0))[:-3]

def fadeInWindow():
    n = 0.01
    while n != 1.0:
        n += 0.01
        root.attributes('-alpha', n)
        root.update()
        time.sleep(FADE_DELAY)

def fadeOutWindow():
    n = 1.0
    while n != 0.01:
        n -= 0.01
        root.attributes('-alpha', n)
        root.update()
        time.sleep(FADE_DELAY)

def getTimeToDisplay():
    currentTime = str(datetime.datetime.now().strftime("%Y-%m-%d \n %H:%M:%S"))
    dayOfTheWeek = datetime.datetime.now().strftime("%A")
    dotwVar.set(dayOfTheWeek)
    timeVar.set(currentTime)
    global oldTime
    if currentTime != oldTime:
        Data.newData = True
        oldTime = currentTime

def listenForAck():
    # CoInitialize COM for this thread (required by WMI/pywin32)
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        try:
            devices = AudioUtilities.GetSpeakers()
            if hasattr(devices, "Activate"):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                volume = None
        except Exception:
            volume = None

        try:
            c = wmi.WMI()
        except Exception:
            c = None

        try:
            t = wmi.WMI(moniker="//./root/wmi")
        except Exception:
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
                    except Exception:
                        pass

                    # Inner loop: listen until we hit a stream error, then break to re-open
                    while not stop.is_set():
                        try:
                            print("listening...")
                            audio = r.listen(source, timeout=None, phrase_time_limit=5)
                            try:
                                text = r.recognize_google(audio).lower()
                            except sr.UnknownValueError:
                                continue
                            except sr.RequestError as e:
                                print("Speech recognition request failed:", e)
                                time.sleep(1)
                                continue

                            print(text)
                            # accept several common variants/short forms
                            if any(k in text for k in ("acknowledge", "acknowledged", "i acknowledge", "ack")):
                                show_withdraw_event.set()
                                Data.newData = False
                        except (OSError, IOError, sr.WaitTimeoutError) as e:
                            # Stream closed or I/O error — break to outer loop and re-open microphone
                            print("listen error (stream closed or I/O):", e)
                            break
                        except Exception as e:
                            print("listen error:", e)
                            time.sleep(0.5)
            except Exception as e:
                print("microphone error (opening):", e)

            # small delay before retrying to open microphone
            time.sleep(1)
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

def openCVMain():
    # open video source
    try:
        src = int(SOURCE)
    except Exception:
        src = SOURCE
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"Cannot open video source: {SOURCE}")
        return

    background = None
    alpha = 0.02
    consec_frames = 0
    # small kernel for morphological opening to remove speckle noise
    morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    print("Starting motion detection. Press 'q' in the window to quit.")
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    recognizer = None
    labels = {}
    try:
        if hasattr(cv2, 'face') and os.path.exists(MODEL_PATH):
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.read(MODEL_PATH)
        elif hasattr(cv2, 'face') and not os.path.exists(MODEL_PATH):
            print('Face recognizer model not found at', MODEL_PATH)
        else:
            print('cv2.face module not available; skipping face recognition')
    except Exception as e:
        print('Error loading recognizer:', e)

    try:
        if os.path.exists(LABELS_PATH):
            with open(LABELS_PATH, 'r', encoding='utf-8') as f:
                labels = json.load(f)
                # labels expected as {"1": "Alice", "2": "Bob"}
    except Exception:
        labels = {}

    openCVMain.last_seen = None
    openCVMain.last_seen_time = 0
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
            except Exception:
                faces = ()

            for (fx, fy, fw, fh) in faces:
                try:
                    face_roi = gray[fy:fy+fh, fx:fx+fw]
                    face_resized = cv2.resize(face_roi, (200, 200))
                except Exception:
                    continue

                if recognizer is not None:
                    try:
                        label_id, confidence = recognizer.predict(face_resized)
                    except Exception:
                        label_id, confidence = None, None
                    name = None
                    if label_id is not None and confidence is not None:
                        if str(label_id) in labels:
                            name = labels.get(str(label_id))
                        else:
                            name = f"id:{label_id}"
                    if name and confidence is not None and confidence < RECOGNITION_CONF_THRESHOLD:
                        cv2.putText(frame, f"{name} ({int(confidence)})", (fx, fy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
                        cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (0, 255, 0), 2)
                        now = time.time()
                        if openCVMain.last_seen != name or (now - openCVMain.last_seen_time) > 5:
                            openCVMain.last_seen = name
                            openCVMain.last_seen_time = now
                            try:
                                root.after(0, lambda n=name: userVar.set(f"Welcome, {n}"))
                            except Exception:
                                pass
                            show_fullscreen_event.set()
                    else:
                        cv2.putText(frame, "Unknown", (fx, fy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
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
                consecFramesNoMotion = 0
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
                consec_no_motion = getattr(openCVMain, "consec_no_motion", 0) + 1
                openCVMain.consec_no_motion = consec_no_motion
            else:
                openCVMain.consec_no_motion = 0

            if getattr(openCVMain, "consec_no_motion", 0) >= 200:
                if not show_fullscreen_event.is_set():
                    print("No motion - requesting fullscreen")
                    show_fullscreen_event.set()
                    openCVMain.consec_no_motion = 0

            getTimeToDisplay()
            
            # if getattr(openCVMain, "consec_no_motion", 0) <= 200:
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
            if not fadedIn:
                fadeInWindow()
            root.lift()
            root.focus_force()
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

def increaseOpacityFrame():
    n = 0.01
    while n != 1.0:
        n += 0.01
        pywinstyles.set_opacity(stuffFrame, n, color=None)
        root.update()
        time.sleep(FADE_DELAY)

def decreaseOpacityFrame():
    n = 1.0
    while n != 0.01:
        n -= 0.01
        pywinstyles.set_opacity(stuffFrame, n, color=None)
        root.update()
        time.sleep(FADE_DELAY)


def moveStuffFrame(stuffFrame):
    stuffFrame.update_idletasks()
    frame_width = stuffFrame.winfo_width()
    frame_height = stuffFrame.winfo_height()

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    max_x = max(0, screen_width - frame_width)
    max_y = max(0, screen_height - frame_height)

    new_x = random.randint(0, max_x)
    new_y = random.randint(0, max_y)
    decreaseOpacityFrame(stuffFrame)

    stuffFrame.place_forget()
    stuffFrame.place(x=new_x, y=new_y)

    increaseOpacityFrame(stuffFrame)
    root.after(20000, lambda: moveStuffFrame(stuffFrame))

stuffFrame = tk.Frame(root)
stuffFrame.configure(bg="black")
stuffFrame.place(x=0, y=0)

root.after(20000, lambda: moveStuffFrame(stuffFrame))

timeVar = tk.StringVar(value="time")
timeLabel = tk.Label(stuffFrame, textvariable=timeVar, fg='white', bg='black', font=('Helvetica', 60))
timeLabel.pack(expand=True)

dotwVar = tk.StringVar(value="dotw")
dotwLabel = tk.Label(stuffFrame, textvariable=dotwVar, fg='white', bg='black', font=('Helvetica', 60))
dotwLabel.pack(expand=True)

global weatherLabel, weatherVar
weatherVar = tk.StringVar(value="weather")
weatherLabel = tk.Label(stuffFrame, textvariable=weatherVar, fg='white', bg='black', font=('Helvetica', 60))
weatherLabel.pack(expand=True)

userVar = tk.StringVar(value="user")
userLabel = tk.Label(stuffFrame, textvariable=userVar, fg='white', bg='black', font=('Helvetica', 60))
userLabel.pack(expand=True)

if __name__ == '__main__':
    root.after(200, _poll_fullscreen)
    root.after(200, _poll_withdraw)
    captureThread = threading.Thread(target=openCVMain, daemon=True)
    listenThread = threading.Thread(target=listenForAck, daemon=True)
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
            pass
        try:
            listenThread.join(timeout=2)
        except Exception:
            pass
        sys.exit()