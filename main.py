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

        try:
            while not stop.is_set():
                with sr.Microphone() as source:
                    print("listening...")
                    audio = r.listen(source)
                text = r.recognize_google(audio).lower()
                print(text)
                if "acknowledge" in text or "acknowledged" in text:
                    show_withdraw_event.set()
        except Exception as e:
            print(e)
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
    if show_fullscreen_event.is_set():
        try:
            root.deiconify()
            root.attributes("-fullscreen", True)
            root.lift()
            root.focus_force()
        except Exception:
            pass
        show_fullscreen_event.clear()
    root.after(200, _poll_fullscreen)


def _poll_withdraw():
    if show_withdraw_event.is_set():
        try:
            root.withdraw()
        except Exception:
            pass
        show_withdraw_event.clear()
    root.after(200, _poll_withdraw)

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