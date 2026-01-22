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
except ImportError as e:
    print(f"You're missing a package. Install with pip. {e}")

SOURCE = 0
MIN_AREA = 500
DISPLAY = True
MIN_CONSECUTIVE = 3

LAT = 49.89
LONG = -97.13

FADE_DELAY = 0.5

global fadedIn

fadedIn = False

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

def getWeather(weatherVar):
    # Run network I/O on a background thread and update Tkinter from main thread.
    def _fetch():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LAT,
            "longitude": LONG,
            "current_weather": True,
            "timezone": "America/Chicago",
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

        # Schedule the UI update on the main thread.
        try:
            root.after(0, lambda: weatherVar.set
                       (f"The temperature at {LAT}, {LONG} is \n {temp if temp is not None else 'N/A'}C°"))
        except Exception:
            # If scheduling fails, ignore — main thread may be shutting down.
            pass

        # Schedule next fetch via the main loop (safe) by starting another background thread
        try:
            root.after(60000, start_fetch_thread)
        except Exception:
            pass

    th = threading.Thread(target=_fetch, daemon=True)
    th.start()


def start_fetch_thread():
    # Helper to kick off a single background weather fetch.
    return getWeather(weatherVar)

# i did this so that i can compare it below, it's only set once as a default
oldTime = str(datetime.datetime.now().replace(microsecond=0))[:-3]

def fadeInWindow():
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.0)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.1)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.2)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.3)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.4)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.5)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.6)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.7)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.8)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.9)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 1.0)
    global fadedIn
    fadedIn = True

def fadeOutWindow():
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 1.0)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.9)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.8)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.7)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.6)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.5)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.4)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.3)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.2)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.1)
    time.sleep(FADE_DELAY)
    root.update()
    root.attributes('-alpha', 0.0)
    global fadedIn
    fadedIn = False

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

def increaseOpacityFrame(stuffFrame):
    # Source - https://stackoverflow.com/a/77850151
    # Posted by Akascape, modified by community. See post 'Timeline' for change history
    # Retrieved 2026-01-21, License - CC BY-SA 4.0

    pywinstyles.set_opacity(stuffFrame, 0.0, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.1, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.2, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.3, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.4, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.5, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.6, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.7, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.8, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.9, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 1.0, color=None)
    root.update()

def decreaseOpacityFrame(stuffFrame):
    pywinstyles.set_opacity(stuffFrame, 1.0, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.9, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.8, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.7, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.6, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.5, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.4, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.3, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.2, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.1, color=None)
    root.update()
    time.sleep(0.5)
    pywinstyles.set_opacity(stuffFrame, 0.0, color=None)
    root.update()

def moveStuffFrame(stuffFrame):
    # Get frame size
    stuffFrame.update_idletasks()
    frame_width = stuffFrame.winfo_width()
    frame_height = stuffFrame.winfo_height()

    # Get screen size
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Calculate valid position (ensure non-negative)
    max_x = max(0, screen_width - frame_width)
    max_y = max(0, screen_height - frame_height)

    # Choose a random position so the frame stays fully within the screen
    new_x = random.randint(0, max_x)
    new_y = random.randint(0, max_y)
    # Fade out while the frame is still visible, then move and fade in.
    decreaseOpacityFrame(stuffFrame)

    # Hide briefly, move to new location, then fade back in.
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

if __name__ == '__main__':
    # start polling GUI events before launching worker
    root.after(200, _poll_fullscreen)
    root.after(200, _poll_withdraw)
    captureThread = threading.Thread(target=openCVMain, daemon=True)
    listenThread = threading.Thread(target=listenForAck, daemon=True)
    captureThread.start()
    listenThread.start()

    # Start the periodic weather fetch on a background thread (UI updates scheduled on main thread)
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