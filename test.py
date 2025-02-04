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

if len(sys.argv) >= 4:
    target_frame_ms = int(sys.argv[3])
else:
    target_frame_ms = 80

if len(sys.argv) >= 3 and sys.argv[2].lower() == "file":
    selected_source = RVM.Sources.OpusFileSource("./docs/speech_stereo.opus", loop=True, target_frame_ms=target_frame_ms)
    # selected_source = RVM.Sources.OpusFileSource("./docs/music_stereo.opus", loop=True, target_frame_ms=target_frame_ms)
    # selected_source = RVM.Sources.OpusFileSource("./docs/podcast.opus", loop=True, target_frame_ms=target_frame_ms)
else:
    selected_source = RVM.Sources.LineSource(target_frame_ms=target_frame_ms)

line_sink   = RVM.Sinks.LineSink()
loopback    = RVM.Sources.Loopback()

if selected_codec.lower() == "raw":
    raw             = RVM.Codecs.Raw()
    input_pipeline  = RVM.Pipeline(source=selected_source, codec=raw, sink=loopback)
    output_pipeline = RVM.Pipeline(source=loopback, codec=raw, sink=line_sink)
elif selected_codec.lower() == "codec2":
    codec2          = RVM.Codecs.Codec2(mode=RVM.Codecs.Codec2.CODEC2_3200)
    input_pipeline  = RVM.Pipeline(source=selected_source, codec=codec2, sink=loopback)
    output_pipeline = RVM.Pipeline(source=loopback, codec=codec2, sink=line_sink)
elif selected_codec.lower() == "opus":
    opus            = RVM.Codecs.Opus()
    input_pipeline  = RVM.Pipeline(source=selected_source, codec=opus, sink=loopback)
    output_pipeline = RVM.Pipeline(source=loopback, codec=opus, sink=line_sink)
else:
    print("No valid codec selected")
    sys.exit(0)

input_pipeline.start(); output_pipeline.start()
input()
input_pipeline.stop()

time.sleep(1)