from pydub import AudioSegment

class Codec():
    preferred_samplerate = None
    frame_quanta_ms      = None
    frame_max_ms         = None
    valid_frame_ms       = None
    source               = None
    sink                 = None

class CodecError(Exception):
    pass

def resample_bytes(sample_bytes, bitdepth, channels, input_rate, output_rate, normalize=False):
    sample_width = bitdepth//8
    audio = AudioSegment(
        sample_bytes,
        frame_rate=input_rate,
        sample_width=sample_width,
        channels=channels)

    if normalize:
        audio = audio.apply_gain(-audio.max_dBFS)

    resampled_audio = audio.set_frame_rate(output_rate)
    return resampled_audio.get_array_of_samples().tobytes()
