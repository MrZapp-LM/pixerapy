#WRITTEN BY: Ted Charles Brown

from PixeraPy import API, Pixera, PixeraError

if __name__ == "__main__":
    ip = "127.0.0.1"  # Replace with your Pixera system's IP address
    port = 1400  # Port of the JSON/TCP API access point in Pixera

    pixera = Pixera(ip, port)

    # ----------------------------- DEFAULT DEBUGGING ---------------------------- #
    print(pixera.send())  # sends "Hello from Python!" to the Pixera log

    # ----------------------------- VERBOSE DEBUGGING ---------------------------- #
    print(pixera.send(API.Utility.outputDebug("Hello from Python!"), verbose=True))

    # ------------------------------- API REVISION ------------------------------- #
    print("Pixera API revision:", pixera.send(API.Utility.getApiRevision()))

    # ---------------------------- CHANGING API METHOD --------------------------- #
    # Needs a second access point in Pixera set to "JSON/TCP (dl)" on port 1401.
    # print(pixera.send(API.Utility.getApiRevision(), protocol="TCP_DL", port=1401))

    # ------------------------- ACCESSING CONTROL MODULES ------------------------ #
    print(pixera.send(["NewModule.Test"]))

    # ---------------------------- MULTIPLE PARAMETERS --------------------------- #
    pixera.send(API.Compound.setTransportModeOnTimeline("Timeline 1", 1))  # play
    pixera.send(API.Compound.setTransportModeOnTimeline("Timeline 1", 0))  # stop

    # ----------------------------- HANDLING HANDLES ----------------------------- #
    for screen in pixera.send(API.Screens.getScreens()):
        print(screen, pixera.send(API.Screens.Screen.getName(screen)))

    # ---------------------------- OPTIONAL PARAMETERS --------------------------- #
    timeline = pixera.send(API.Timelines.getTimelineFromName("Timeline 1"))
    layer = pixera.send(API.Timelines.Timeline.getLayerFromName(timeline, "Layer 1"))
    pixera.send(API.Timelines.Layer.setOpacity(layer, 0.5, fadeTimeMs=2000))  # fade over 2 s
    pixera.send(API.Timelines.Layer.setOpacity(layer, 1.0))  # fadeTimeMs left out

    # ---------------------------------- ERRORS ---------------------------------- #
    try:
        pixera.send(["Pixera.Does.notExist"])
    except PixeraError as error:
        print("Pixera error:", error)

    # ------------------------------- MANUAL INPUT ------------------------------- #
    print(pixera.send(["Pixera.Utility.outputDebug", ["message"], ["Hello from Python!"]]))
