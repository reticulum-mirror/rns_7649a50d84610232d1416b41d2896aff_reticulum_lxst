import LXST
import time
import os

from LXST.Sinks import LineSink
from LXST.Sources import OpusFileSource

class FilePlayer():
    def __init__(self, path=None, device=None, loop=False):
        self._file_path = path
        self._playback_device = None
        self.__loop = loop
        self.__source = None
        self.__sink = LineSink(self._playback_device)
        self.__raw             = LXST.Codecs.Raw()
        self.__loopback        = LXST.Sources.Loopback()
        self.__output_pipeline = LXST.Pipeline(source=self.__loopback, codec=self.__raw, sink=self.__sink)
        self.__input_pipeline  = None
        if path: self.set_source(self._file_path)

    @property
    def running(self):
        if not self.__source: return False
        else: return self.__source.should_run

    @property
    def playing(self): return self.running

    def set_source(self, path=None):
        if not path: return
        else:
            if not os.path.isfile(path): raise OSError(f"File not found: {path}")
            else:
                self.__source = OpusFileSource(path, loop=self.__loop)
                self.__input_pipeline = LXST.Pipeline(source=self.__source, codec=self.__raw, sink=self.__loopback)

    def loop(self, loop=True):
        if loop == True: self.__loop = True
        else: self.__loop = False
        if self.__source: self.__source.loop = self.__loop

    def start(self):
        if self.__source:
            self.__input_pipeline.start()
            self.__output_pipeline.start()

    def stop(self):
        if self.__source:
            self.__input_pipeline.stop()
            self.__output_pipeline.stop()

    def play(self): self.start()