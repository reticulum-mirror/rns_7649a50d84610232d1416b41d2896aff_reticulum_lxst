import RNS
import RVM
import time
RNS.loglevel = RNS.LOG_DEBUG

line_source = RVM.Sources.LineSource(target_frame_ms=70)
line_sink   = RVM.Sinks.LineSink()
loopback    = RVM.Sources.Loopback()
raw_codec   = RVM.Codecs.Raw()

input_pipeline  = RVM.Pipeline(source=line_source, codec=raw_codec, sink=loopback)
output_pipeline = RVM.Pipeline(source=loopback, codec=raw_codec, sink=line_sink)

input_pipeline.start(); output_pipeline.start()
input()
input_pipeline.stop(); output_pipeline.stop()

time.sleep(0.5)