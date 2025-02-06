import RNS
import RVM
import sys
import time
RNS.loglevel = RNS.LOG_DEBUG

target_frame_ms = 2.5

raw         = RVM.Codecs.Raw()
opus        = RVM.Codecs.Opus(profile=RVM.Codecs.Opus.PROFILE_AUDIO_MEDIUM)

line_sink1   = RVM.Sinks.LineSink()
line_sink2   = RVM.Sinks.LineSink()
mixer1       = RVM.Mixer(sink=line_sink1, target_frame_ms=target_frame_ms)
mixer2       = RVM.Mixer(sink=line_sink2, target_frame_ms=target_frame_ms)
file_source1 = RVM.Sources.OpusFileSource("./docs/speech_stereo.opus", codec=raw, sink=mixer1, loop=True, target_frame_ms=target_frame_ms)
file_source2 = RVM.Sources.OpusFileSource("./docs/podcast.opus", codec=raw, sink=mixer1, loop=True, target_frame_ms=target_frame_ms)
# line_source  = RVM.Sources.LineSource(target_frame_ms=target_frame_ms, codec=raw, sink=mixer)

# mixer1.start()
# file_source1.start()
# input()
# mixer2.start()
# file_source2.start()

mixer1.start()
input()
file_source1.start()
input()
file_source2.start()
input()
file_source1.stop()
file_source2.stop()
RNS.log("STOPPED")
# line_source.start()

input()
