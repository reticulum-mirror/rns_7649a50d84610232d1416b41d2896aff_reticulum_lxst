import RNS
import LXST
import time
import os
from LXST.Sources import LineSource
from LXST.Sinks import OpusFileSink

class FileRecorder():
    def __init__(self, path=None, device=None, profile=LXST.Codecs.Opus.PROFILE_AUDIO_MAX):
        self._file_path = path
        self._record_device = device
        self.__profile = profile
        self.__source = None
        self.__sink = OpusFileSink(path=self._file_path, profile=profile)
        self.__null = LXST.Codecs.Null()
        self.set_source(device)

    @property
    def running(self):
        if not self.__source: return False
        else: return self.__source.should_run

    @property
    def recording(self): return self.running

    def set_source(self, device=None):
        self._record_device = device
        self.__source = LineSource(preferred_device=self._record_device, target_frame_ms=60, codec=self.__null, sink=self.__sink)
        self.__sink.source = self.__source

    def set_output_path(self, path):
        self._file_path = path
        self.__sink.__output_path = path

    def start(self):
        if self.__source:
            self.__source.start()

    def stop(self):
        if self.__source:
            self.__source.stop()
            while self.__sink.frames_waiting: time.sleep(0.1)
            self.__sink.stop()

    def record(self): 
        self.start()