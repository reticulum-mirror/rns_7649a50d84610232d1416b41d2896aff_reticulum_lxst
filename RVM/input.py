import RNS
import math
import threading
from collections import deque
RNS.loglevel = RNS.LOG_DEBUG

class LinuxBackend():
    SAMPLERATE = 48000

    def __init__(self, samplerate=SAMPLERATE):
        import soundcard
        self.soundcard  = soundcard
        self.microphone = soundcard.default_microphone()
        self.samplerate = samplerate
        RNS.log(f"Using microphone {self.microphone}", RNS.LOG_DEBUG)

    def flush(self):
        self.recorder.flush()

    def get_recorder(self, samples_per_frame):
        return self.microphone.recorder(samplerate=self.SAMPLERATE, blocksize=samples_per_frame)


class Input():
    MAX_FRAMES = 128

    def __init__(self, target_frame_ms=70):
        self.frame_deque = deque(maxlen=self.MAX_FRAMES)
        self.should_ingest = False
        self.ingest_thread = None
        self.backend = LinuxBackend()
        self.recording_lock = threading.Lock()
        self.samples_per_frame = math.ceil((1/target_frame_ms)*self.backend.samplerate)

    def start(self):
        if not self.should_ingest:
            self.should_ingest = True
            self.ingest_thread = threading.Thread(target=self.__ingest_job, daemon=True)
            self.ingest_thread.start()

    def stop(self):
        self.should_ingest = False

    def __ingest_job(self):
        with self.recording_lock:
            frame_samples = None
            with self.backend.get_recorder(samples_per_frame=self.samples_per_frame) as recorder:
                while self.should_ingest:
                    frame_samples = recorder.record(numframes=self.samples_per_frame)
