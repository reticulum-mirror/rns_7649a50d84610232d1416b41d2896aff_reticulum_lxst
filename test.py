import RNS
import RVM
import sys
import time
RNS.loglevel = RNS.LOG_DEBUG

if len(sys.argv) < 2:
    print("No codec specified")
    sys.exit(0)
else:
    selected_codec = sys.argv[1]

if len(sys.argv) >= 3:
    target_frame_ms = int(sys.argv[2])
else:
    target_frame_ms = 80

line_source = RVM.Sources.LineSource(target_frame_ms=target_frame_ms)
line_sink   = RVM.Sinks.LineSink()
loopback    = RVM.Sources.Loopback()
raw_codec   = RVM.Codecs.Raw()
codec2      = RVM.Codecs.Codec2()

if selected_codec.lower() == "raw":
    input_pipeline  = RVM.Pipeline(source=line_source, codec=raw_codec, sink=loopback)
    output_pipeline = RVM.Pipeline(source=loopback, codec=raw_codec, sink=line_sink)
elif selected_codec.lower() == "codec2":
    input_pipeline  = RVM.Pipeline(source=line_source, codec=codec2, sink=loopback)
    output_pipeline = RVM.Pipeline(source=loopback, codec=codec2, sink=line_sink)
else:
    print("No valid codec selected")
    sys.exit(0)

input_pipeline.start(); output_pipeline.start()
input()
input_pipeline.stop()

time.sleep(1)