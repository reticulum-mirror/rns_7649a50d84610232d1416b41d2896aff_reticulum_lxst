import RNS
import RVM
import sys
import time
RNS.loglevel = RNS.LOG_DEBUG

target_frame_ms = 20

raw          = RVM.Codecs.Raw()

line_sink    = RVM.Sinks.LineSink()
mixer        = RVM.Mixer(sink=line_sink, target_frame_ms=target_frame_ms)
file_source1 = RVM.Sources.OpusFileSource("./docs/speech_stereo.opus", codec=raw, sink=mixer, loop=True, target_frame_ms=target_frame_ms)
file_source2 = RVM.Sources.OpusFileSource("./docs/podcast.opus", codec=raw, sink=mixer, loop=True, target_frame_ms=target_frame_ms)
line_source  = RVM.Sources.LineSource(target_frame_ms=target_frame_ms, codec=raw, sink=mixer)

mixer.start()
line_source.start()
print("Hit enter to add another source"); input()
file_source1.start()
print("Hit enter to add another source"); input()
file_source2.start()
print("Hit enter to stop all sources"); input()
file_source1.stop()
file_source2.stop()
line_source.stop()

time.sleep(0.5)