from .Sources import *
from .Sinks   import *
from .Codecs  import *

class PipelineError(Exception):
    pass

class Pipeline():
    def __init__(self, source, codec, sink, processor = None):
        if not issubclass(type(source), Source): raise PipelineError("Audio pipeline initialised with invalid source")
        if not issubclass(type(sink), Sink)    : raise PipelineError("Audio pipeline initialised with invalid sink")
        if not issubclass(type(codec), Codec)  : raise PipelineError("Audio pipeline initialised with invalid codec")
        self.source              = source
        self.source.codec        = codec
        self.source.sink         = sink
        self.source.codec.sink   = sink
        self.source.codec.source = source

        if isinstance(sink, Loopback):
            sink.samplerate = source.samplerate

    @property
    def codec(self):
        if self.source:
            return self.source.codec
        else:
            return None

    @property
    def sink(self):
        if self.source:
            return self.source.sink
        else:
            return None

    @property
    def running(self):
        return self.source.should_run

    def start(self):
        if not self.running:
            self.source.start()

    def stop(self):
        if self.running:
            self.source.stop()