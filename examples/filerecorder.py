import sys
import time
import select
from LXST.Primitives.Recorders import FileRecorder

filename = "recording.opus"

recorder = FileRecorder(filename)
recorder.start()
print("Recording started")

try: input()
except KeyboardInterrupt: pass

recorder.stop()
time.sleep(0.5)
print(f"Recording saved to {filename}")