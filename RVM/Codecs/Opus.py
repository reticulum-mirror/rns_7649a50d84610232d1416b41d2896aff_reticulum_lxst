import io
import time
import math
import numpy as np
from .Codec import Codec, CodecError
from .libs.pyogg import OpusEncoder, OpusDecoder

class Opus(Codec):
    FRAME_QUANTA_MS = 2.5
    FRAME_MAX_MS    = 60
    VALID_FRAME_MS  = [2.5, 5, 10, 20, 40, 60]
    TYPE_MAP_FACTOR = np.iinfo("int16").max

    def __init__(self, mode="voip"):
        self.frame_quanta_ms = self.FRAME_QUANTA_MS
        self.frame_max_ms    = self.FRAME_MAX_MS
        self.valid_frame_ms  = self.VALID_FRAME_MS
        self.channels = 1
        self.bitdepth = 16
        self.opus_encoder = OpusEncoder()
        self.opus_decoder = OpusDecoder()
        self.encoder_configured = False
        self.decoder_configured = False
        self.set_mode(mode)

    def set_mode(self, mode):
        self.mode = mode
        self.opus_encoder.set_application(self.mode)

    def encode(self, frame):
        if frame.shape[1] == 0:
            raise CodecError("Cannot encode frame with 0 channels")
        elif frame.shape[1] > self.channels:
            frame = frame[:, 1]

        input_samples = frame*self.TYPE_MAP_FACTOR
        input_samples = input_samples.astype(np.int16)

        frame_duration_ms = len(input_samples)/self.source.samplerate
        input_samples = frame*self.TYPE_MAP_FACTOR
        input_samples = input_samples.astype(np.int16)

        if not self.encoder_configured:
            self.opus_encoder.set_sampling_frequency(self.source.samplerate)
            self.opus_encoder.set_channels(1)
            self.encoder_configured = True

        return self.opus_encoder.encode(input_samples.tobytes()).tobytes()

    def decode(self, frame_bytes):
        if not self.decoder_configured:
            self.opus_decoder.set_channels(self.channels)
            self.opus_decoder.set_sampling_frequency(self.sink.samplerate)
            self.decoder_configured = True

        decoded_frame_bytes = self.opus_decoder.decode(memoryview(bytearray(frame_bytes)))
        decoded_samples = np.frombuffer(decoded_frame_bytes, dtype="int16")/self.TYPE_MAP_FACTOR
        frame_samples = np.zeros((len(decoded_samples), 1), dtype="float32")
        frame_samples[:, 0] = decoded_samples

        return frame_samples