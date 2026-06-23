import RNS
import LXST
import time
import sys
import os
from LXST.Codecs import Raw, Opus, Null
from LXST.Sources import OpusFileSource, LineSource
from LXST.Sinks import LineSink, OpusFileSink
from LXST.Mixer import Mixer
from LXST.Pipeline import Pipeline
from LXST.Filters import EchoCanceller, BandPass, AGC

RNS.loglevel = RNS.LOG_DEBUG

raw=Raw()
target_frame_ms=40
input_file = "docs/speech.opus"
output_file = "tests/echo_test_recording.opus"

echo_canceller = EchoCanceller()

line_sink    = LineSink()
mixer        = Mixer(target_frame_ms=target_frame_ms, sink=line_sink, gain=0.0)
file_source  = OpusFileSource("./docs/speech.opus", codec=raw, sink=mixer, loop=True, target_frame_ms=target_frame_ms)
mixer.reference_outs = [echo_canceller]

filter_chain = []
filter_chain.append(BandPass(350, 6500))
filter_chain.append(AGC(target_level=-15.0))
filter_chain.append(echo_canceller)
filter_chain.append(BandPass(350, 5500))

recording_sink = OpusFileSink(path=output_file)
mic_source = LineSource(target_frame_ms=60, codec=Raw(), filters=filter_chain, skip=0.075, ease_in=0.0)
output_pipeline = Pipeline(source=mic_source, codec=Null(), sink=recording_sink)

mixer.start()
file_source.start()
mic_source.start()

print("Press Ctrl+C to stop")

try:
    while True: time.sleep(0.2)
except KeyboardInterrupt: pass

file_source.stop()
mic_source.stop()
time.sleep(0.5)
recording_sink.stop()
print(f"Recording saved to {output_file}")