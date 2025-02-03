import RNS
import math
import threading
from collections import deque
from .Sinks import LocalSink
from .Codecs import Codec, CodecError

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

class LocalSource(Source):
    pass

class RemoteSource(Source):
    pass

class Loopback(LocalSource, LocalSink):
    MAX_FRAMES = 128

    def __init__(self, target_frame_ms=70, codec=None, sink=None):
        self.frame_deque     = deque(maxlen=self.MAX_FRAMES)
        self.should_run      = False
        self.loopback_thread = None
        self.loopback_lock   = threading.Lock()
        self.codec           = codec
        self._sink           = sink
        self._source         = None

    def start(self):
        if not self.should_run:
            RNS.log(f"{self} starting", RNS.LOG_DEBUG)
            self.should_run = True

    def stop(self):
        self.should_run = False

    def handle_frame(self, frame):
        with self.loopback_lock:
            if self.codec and self.sink:
                self.sink.handle_frame(self.codec.decode(frame))

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, source):
        self._source = source

class LineSource(LocalSource):
    MAX_FRAMES = 128

    def __init__(self, target_frame_ms=70, codec=None, sink=None):
        self.frame_deque     = deque(maxlen=self.MAX_FRAMES)
        self.target_frame_ms = target_frame_ms
        self.should_run      = False
        self.ingest_thread   = None
        self.recording_lock  = threading.Lock()
        self._codec          = None
        self.codec           = codec
        self.sink            = sink

    @property
    def codec(self):
        return self._codec

    @codec.setter
    def codec(self, codec):
        if codec == None:
            self._codec = None
        elif not issubclass(type(codec), Codec):
            raise CodecError(f"Invalid codec specified for {self}")
        else:
            self._codec = codec

            if self.codec.preferred_samplerate:
                self.preferred_samplerate = self.codec.preferred_samplerate
            else:
                self.preferred_samplerate = Backend.SAMPLERATE

            if self.codec.frame_quanta_ms:
                if self.target_frame_ms%self.codec.frame_quanta_ms != 0:
                    self.target_frame_ms = math.ceil(self.target_frame_ms/self.codec.frame_quanta_ms)*self.codec.frame_quanta_ms
                    RNS.log(f"{self} target frame time quantized to {self.target_frame_ms}ms due to codec frame quanta", RNS.LOG_DEBUG)
            
            if self.codec.frame_max_ms:
                if self.target_frame_ms > self.codec.frame_max_ms:
                    self.target_frame_ms = self.codec.frame_max_ms
                    RNS.log(f"{self} target frame time clamped to {self.target_frame_ms}ms due to codec frame limit", RNS.LOG_DEBUG)

            if self.codec.valid_frame_ms:
                if not self.target_frame_ms in self.codec.valid_frame_ms:
                    self.target_frame_ms = min(self.codec.valid_frame_ms, key=lambda t:abs(t-self.target_frame_ms))
                    RNS.log(f"{self} target frame time clamped to closest valid value of {self.target_frame_ms}ms ", RNS.LOG_DEBUG)

            self.backend           = Backend(samplerate=self.preferred_samplerate)
            self.samplerate        = self.backend.samplerate
            self.samples_per_frame = math.ceil((self.target_frame_ms/1000)*self.samplerate)

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
                    if self.codec:
                        frame = self.codec.encode(frame_samples)
                        if self.sink:
                            self.sink.handle_frame(frame)

class PacketSource(RemoteSource):
    pass