import RNS
import math
import time
import threading
from collections import deque
RNS.loglevel = RNS.LOG_DEBUG

class LinuxBackend():
    SAMPLERATE = 48000

    def __init__(self, samplerate=SAMPLERATE):
        import soundcard
        self.soundcard  = soundcard
        self.device     = soundcard.default_speaker()
        self.samplerate = samplerate
        RNS.log(f"Using output device {self.device}", RNS.LOG_DEBUG)

    def flush(self):
        self.recorder.flush()

    def get_player(self, samples_per_frame=None):
        return self.device.player(samplerate=self.SAMPLERATE, blocksize=samples_per_frame)

def get_backend():
    if RNS.vendor.platformutils.is_linux():
        return LinuxBackend
    else:
        return None

Backend = get_backend()

class Sink():
    def handle_frame(self, frame):
        pass

class RemoteSink(Sink):
    pass

class LocalSink(Sink):
    pass

class LineSink(LocalSink):
    MAX_FRAMES    = 128
    AUTOSTART_MIN = 2
    FRAME_TIMEOUT = 8

    def __init__(self, autodigest=True):
        self.frame_deque          = deque(maxlen=self.MAX_FRAMES)
        self.should_run           = False
        self.digest_thread        = None
        self.digest_lock          = threading.Lock()
        self.frame_deque          = deque(maxlen=self.MAX_FRAMES)
        self.underrun_at          = None
        self.frame_timeout        = self.FRAME_TIMEOUT
        self.autodigest           = autodigest
        self.autostart_min        = self.AUTOSTART_MIN
        
        self.preferred_samplerate = Backend.SAMPLERATE
        self.backend              = Backend(samplerate=self.preferred_samplerate)

        self.samples_per_frame    = None
        self.frame_time           = None

    def handle_frame(self, frame):
        self.frame_deque.append(frame)
        if self.samples_per_frame == None:
            self.samples_per_frame = len(frame)
            self.frame_time = self.samples_per_frame*(1/self.backend.samplerate)
            RNS.log(f"{self} starting at {self.samples_per_frame} samples per frame", RNS.LOG_DEBUG)

        if self.autodigest and not self.should_run:
            if len(self.frame_deque) >= self.autostart_min:
                self.start()

    def start(self):
        if not self.should_run:
            self.should_run = True
            self.digest_thread = threading.Thread(target=self.__digest_job, daemon=True)
            self.digest_thread.start()

    def stop(self):
        self.should_run = False

    def __digest_job(self):
        with self.digest_lock:
            with self.backend.get_player(samples_per_frame=self.samples_per_frame) as player:
                while self.should_run:
                    frames_ready = len(self.frame_deque)
                    if frames_ready:
                        self.underrun_at = None
                        player.play(self.frame_deque.pop())
                        if len(self.frame_deque) > 2:
                            RNS.log(f"Buffer lag on {self}, dropping one frame", RNS.LOG_DEBUG)
                            self.frame_deque.pop()
                    else:
                        time.sleep(self.frame_time*1.1)
                        if self.underrun_at == None:
                            RNS.log(f"Buffer underrun on {self}", RNS.LOG_DEBUG)
                            self.underrun_at = time.time()
                        else:
                            if time.time() > self.underrun_at+(self.frame_time*self.frame_timeout):
                                RNS.log(f"No frames available on {self}, stopping playback", RNS.LOG_DEBUG)
                                self.should_run = False
