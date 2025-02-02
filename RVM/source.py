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
        self.device     = soundcard.default_microphone()
        self.samplerate = samplerate
        RNS.log(f"Using input device {self.device}", RNS.LOG_DEBUG)

    def flush(self):
        self.recorder.flush()

    def get_recorder(self, samples_per_frame):
        return self.device.recorder(samplerate=self.SAMPLERATE, blocksize=samples_per_frame)

def get_backend():
    if RNS.vendor.platformutils.is_linux():
        return LinuxBackend
    else:
        return None

Backend = get_backend()

class Source():
    pass

class LineSource(Source):
    MAX_FRAMES = 128

    def __init__(self, target_frame_ms=70, encoder=None, sink=None):
        self.frame_deque    = deque(maxlen=self.MAX_FRAMES)
        self.should_run     = False
        self.ingest_thread  = None
        self.recording_lock = threading.Lock()
        self.encoder        = encoder
        self.sink           = sink
        
        if self.encoder != None and self.encoder.preferred_samplerate:
            self.preferred_samplerate = self.encoder.preferred_samplerate
        else:
            self.preferred_samplerate = Backend.SAMPLERATE

        self.backend           = Backend(samplerate=self.preferred_samplerate)
        self.samples_per_frame = math.ceil((target_frame_ms/1000)*self.backend.samplerate)

    def start(self):
        if not self.should_run:
            RNS.log(f"{self} starting at {self.samples_per_frame} samples per frame", RNS.LOG_DEBUG)
            self.should_run = True
            self.ingest_thread = threading.Thread(target=self.__ingest_job, daemon=True)
            self.ingest_thread.start()

    def stop(self):
        self.should_run = False

    def __ingest_job(self):
        with self.recording_lock:
            frame_samples = None
            with self.backend.get_recorder(samples_per_frame=self.samples_per_frame) as recorder:
                while self.should_run:
                    frame_samples = recorder.record(numframes=self.samples_per_frame)
                    if self.encoder:
                        frame = self.encoder.encode(frame_samples)
                        if self.sink:
                            self.sink.handle_frame(frame)
