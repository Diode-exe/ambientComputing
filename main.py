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

# Minimal motion detector (no argparse). Configure constants below.
SOURCE = 0            # camera index or video file path
MIN_AREA = 500        # minimum contour area to consider motion
DISPLAY = True
MIN_CONSECUTIVE = 3   # require motion for this many consecutive frames before reporting

# Event used to request fullscreen from the GUI/main thread
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

# i did this so that i can compare it below, it's only set once as a default
oldTime = str(datetime.datetime.now().replace(microsecond=0))[:-3]

def fadeInWindow():
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.1)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.2)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.3)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.4)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.5)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.6)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.7)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.8)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.9)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 1.0)

def fadeOutWindow():
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 1.0)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.9)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.8)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.7)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.6)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.5)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.4)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.3)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.2)
    time.sleep(0.5)
    root.update()
    root.attributes('-alpha', 0.1)

def getTimeToDisplay():
    currentTime = str(datetime.datetime.now().replace(microsecond=0))[:-3]
    timeVar.set(currentTime)
    global oldTime
    if currentTime != oldTime:
        Data.newData = True
        oldTime = currentTime

# Get audio endpoint volume if available
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

                while not stop.is_set():
                    try:
                        print("listening...")
                        # limit phrase length to avoid excessively long captures
                        audio = r.listen(source, timeout=None, phrase_time_limit=5)
                        try:
                            text = r.recognize_google(audio).lower()
                        except sr.UnknownValueError:
                            # could not understand audio
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
                    except Exception as e:
                        print("listen error:", e)
                        time.sleep(0.5)
        except Exception as e:
            print("microphone error:", e)
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
    try:
        while not stop.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

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

timeVar = tk.StringVar(value="time")
timeLabel = tk.Label(root, textvariable=timeVar, fg='white', bg='black', font=('Helvetica', 96))
timeLabel.pack(expand=True)

if __name__ == '__main__':
    # start polling GUI events before launching worker
    root.after(200, _poll_fullscreen)
    root.after(200, _poll_withdraw)
    captureThread = threading.Thread(target=openCVMain, daemon=True)
    listenThread = threading.Thread(target=listenForAck, daemon=True)
    captureThread.start()
    listenThread.start()

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