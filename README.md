
# ambientComputing

Make computers more inviting and/or personal

Saying acknowledge will close the info screen

This has crashed my computer and I don't know why, so be careful.

## I assume ZERO RESPONSIBILITY for any issues that may occur

### Quirks

For some reason, if you stop the program in the middle of the fade transition, it'll raise a ValueError

Saying acknowledge will dismiss the window for 200 frames. I need to make it so that there is new data, maybe

It really should switch every 2 minutes, but it doesn't for testing

### How do I make this work?

Great question. You need to have a folder structure of ```projectFolder/dataset/nameOfPersonToTrain/name1.jpg```

It doesn't have to be a .jpg file, as long as it's a picture. Then run the command in train.txt, making sure to
navigate to your project folder in your terminal. It will train, and then you can run main.py.

### Warning

This is not an easy program to run! The face recognition makes OpenCV choppy even on my laptop with a Core Ultra 9 185H! You have been warned!

### This is not completely local

Some parts of this program use online APIs, such as the TTS system. Be aware of this if you are concerned about privacy. The face recognition is completely local, however.
