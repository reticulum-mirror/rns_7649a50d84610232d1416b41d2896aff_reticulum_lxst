import RVM
import time

line_source = RVM.source.LineSource(target_frame_ms=70)
line_sink   = RVM.sink.LineSink()
loopback    = RVM.source.Loopback()
raw_codec   = RVM.codecs.Raw()

input_pipeline  = RVM.Pipeline(source=line_source, codec=raw_codec, sink=loopback)
output_pipeline = RVM.Pipeline(source=loopback, codec=raw_codec, sink=line_sink)

input_pipeline.start(); output_pipeline.start()
input()
input_pipeline.stop(); output_pipeline.stop()

time.sleep(0.5)