import RNS
import RVM
import sys
import time
RNS.loglevel = RNS.LOG_DEBUG

target_frame_ms  = 20
pipelined_output = False
raw              = RVM.Codecs.Raw()

# Pipelined mixer example
if pipelined_output:
    opus         = RVM.Codecs.Opus(profile=RVM.Codecs.Opus.PROFILE_AUDIO_HIGH)
    line_sink    = RVM.Sinks.LineSink()
    mixer        = RVM.Mixer(target_frame_ms=target_frame_ms)
    loopback     = RVM.Sources.Loopback()
    
    file_source1 = RVM.Sources.OpusFileSource("./docs/speech_stereo.opus", codec=raw, sink=mixer, loop=True, target_frame_ms=target_frame_ms)
    file_source2 = RVM.Sources.OpusFileSource("./docs/podcast.opus", codec=raw, sink=mixer, loop=True, target_frame_ms=target_frame_ms)
    line_source  = RVM.Sources.LineSource(target_frame_ms=target_frame_ms, codec=raw, sink=mixer)

    input_pipeline  = RVM.Pipeline(source=mixer, codec=opus, sink=loopback)
    output_pipeline = RVM.Pipeline(source=loopback, codec=opus, sink=line_sink)
    input_pipeline.start(); output_pipeline.start()

# Simple mixer example with output directly to sink
else:
    line_sink    = RVM.Sinks.LineSink()
    mixer        = RVM.Mixer(target_frame_ms=target_frame_ms, sink=line_sink)
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