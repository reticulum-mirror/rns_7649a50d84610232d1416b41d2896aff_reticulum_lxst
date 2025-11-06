import atexit
import collections.abc
import time
import re
import threading
import numpy
import RNS

if RNS.vendor.platformutils.get_platform() == "android":
    try: from jnius import autoclass, cast
    except Exception as e:
        RNS.log(f"Could load module for native Java interface access on Android: {e}")
        raise e

class _AndroidAudio:

    def __init__(self): self._client_name = None
    def _shutdown(self): pass

    @property
    def name(self): return self._client_name

    @name.setter
    def name(self, name): self._client_name = name

    @property
    def source_list(self):
        # TODO: Fetch source list through JNI
        info = [{"name": "Mock Source", "id": "mocksource0"}]
        return info

    def source_info(self, id):
        # TODO: Fetch source info for matched sources through JNI
        mock_source = {'latency': 0, 'configured_latency': 0, 'channels': 2, 'name': 'Mock Source', 'device.class': 'sound', 'device.api': 'alsa', 'device.bus': 'pci'}
        info = [mock_source]
        return info[0] # Only first/best match

    @property
    def sink_list(self):
        # TODO: Fetch sink list through JNI
        info = [{"name": "Mock Sink", "id": "mocksink0"}]
        return info

    def sink_info(self, id):
        # TODO: Fetch sink info for matched sinks through JNI
        mock_sink = {'latency': 0, 'configured_latency': 0, 'channels': 2, 'name': 'Mock Sink', 'device.class': 'sound', 'device.api': 'alsa', 'device.bus': 'pci'}
        info = [mock_sink]
        return info[0] # Only first/best match

    @property
    def server_info(self):
        # TODO: Fetch server/context info through JNI
        mock_server = {'server version': '1.0.0', 'server name': 'Mock Android audio server', 'default sink id': 'mocksink0', 'default source id': 'mocksource0'}
        info = mock_server
        return info

_audio = _AndroidAudio()
atexit.register(_audio._shutdown)

def all_speakers(): return [_Speaker(id=s['id']) for s in _audio.sink_list]

def default_speaker():
    name = _audio.server_info["default sink id"]
    return get_speaker(name)

def get_speaker(id):
    speakers = _audio.sink_list
    return _Speaker(id=_match_soundcard(id, speakers)['id'])

def all_microphones(include_loopback=False, exclude_monitors=True):
    if not exclude_monitors: include_loopback = not exclude_monitors
    mics = [_Microphone(id=m['id']) for m in _audio.source_list]
    if not include_loopback: return [m for m in mics if m._get_info()['device.class'] != 'monitor']
    else: return mics

def default_microphone():
    name = _audio.server_info['default source id']
    return get_microphone(name, include_loopback=True)

def get_microphone(id, include_loopback=False, exclude_monitors=True):
    if not exclude_monitors: include_loopback = not exclude_monitors
    microphones = _audio.source_list
    return _Microphone(id=_match_soundcard(id, microphones, include_loopback)['id'])

def _match_soundcard(id, soundcards, include_loopback=False):
    if not include_loopback:
        soundcards_by_id = {soundcard['id']: soundcard for soundcard in soundcards if not 'monitor' in soundcard['id']}
        soundcards_by_name = {soundcard['name']: soundcard for soundcard in soundcards if not 'monitor' in soundcard['id']}
    else:
        soundcards_by_id = {soundcard['id']: soundcard for soundcard in soundcards}
        soundcards_by_name = {soundcard['name']: soundcard for soundcard in soundcards}
    
    if id in soundcards_by_id: return soundcards_by_id[id]

    for name, soundcard in soundcards_by_name.items():
        if id in name: return soundcard
    
    pattern = ".*".join(id)
    for name, soundcard in soundcards_by_name.items():
        if re.match(pattern, name): return soundcard
    raise IndexError(f"no soundcard with id {id}")

def get_name(): return _audio.name

def set_name(name): _audio.name = name


class _SoundCard:
    def __init__(self, *, id):
        self._id = id

    @property
    def channels(self): return self._get_info()['channels']

    @property
    def id(self): return self._id

    @property
    def name(self): return self._get_info()['name']

    def _get_info(self): return _audio.source_info(self._id)


class _Speaker(_SoundCard):

    def __repr__(self):
        return '<Speaker {} ({} channels)>'.format(self.name, self.channels)

    def player(self, samplerate, channels=None, blocksize=None):
        if channels is None: channels = self.channels
        return _Player(self._id, samplerate, channels, blocksize)

    def play(self, data, samplerate, channels=None, blocksize=None):
        if channels is None: channels = self.channels
        with _Player(self._id, samplerate, channels, blocksize) as s: s.play(data)

    def _get_info(self): return _audio.sink_info(self._id)


class _Microphone(_SoundCard):

    def __repr__(self):
        if self.isloopback: return '<Loopback {} ({} channels)>'.format(self.name, self.channels)
        else:               return '<Microphone {} ({} channels)>'.format(self.name, self.channels)

    @property
    def isloopback(self):
        return False

    def recorder(self, samplerate, channels=None, blocksize=None):
        if channels is None: channels = self.channels
        return _Recorder(self._id, samplerate, channels, blocksize)

    def record(self, numframes, samplerate, channels=None, blocksize=None):
        if channels is None: channels = self.channels
        with _Recorder(self._id, samplerate, channels, blocksize) as r: return r.record(numframes)


class _Stream:
    TYPE_MAP_FACTOR = numpy.iinfo("int16").max

    def __init__(self, id, samplerate, channels, blocksize=None, name='outputstream'):
        self._id = id
        self._samplerate = samplerate
        self._name = name
        self._blocksize = blocksize
        self.channels = channels
        self.bit_depth = 16
        self.audio_track = None

        try:
            Context = autoclass('android.content.Context')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            self.AudioManager        = activity.getSystemService(autoclass("android.media.AudioManager"))
            self.AudioTrack          = autoclass("android.media.AudioTrack")
            self.AudioFormat         = autoclass("android.media.AudioFormat")

            self.audio_encoding      = self.AudioFormat.ENCODING_PCM_16BIT
            self.audio_track_mode    = self.AudioTrack.MODE_STREAM
            self.audio_track_profile = self.AudioManager.STREAM_MUSIC # STREAM_VOICE_CALL, STREAM_RING, STREAM_NOTIFICATION
            
            if self.channels == 1:
                self.audio_format_out = self.AudioFormat.CHANNEL_IN_MONO
                self.audio_format_in  = self.AudioFormat.CHANNEL_IN_MONO
            
            elif self.channels == 2:
                self.audio_format_out = self.AudioFormat.CHANNEL_OUT_STEREO
                self.audio_format_in  = self.AudioFormat.CHANNEL_OUT_STEREO

            else: raise ValueError(f"Unsupported channel count {channels} on Android audio backend")

            self.min_buffer_playback  = self.AudioTrack.getMinBufferSize(self._samplerate, self.audio_format_out, self.audio_encoding);
            self.min_buffer_recording = self.AudioTrack.getMinBufferSize(self._samplerate, self.audio_format_in, self.audio_encoding);
            self.bytes_per_sample = (self.bit_depth//8)*self.channels

            self._samplerate = int(self.AudioManager.getProperty(self.AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE))
        
        except Exception as e:
            RNS.log(f"Could not initialize Android audio context for {self}: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    def __enter__(self):
        if isinstance(self.channels, collections.abc.Iterable): channel_count = len(self.channels)
        elif isinstance(self.channels, int): channel_count = self.channels
        else: raise TypeError('channels must be iterable or integer')
        
        numchannels = self.channels if isinstance(self.channels, int) else len(self.channels)
        self._connect_stream()
        if not self.audio_track and not self.audio_record:
            RNS.log(f"Failed to acquire audio stream for {self}", RNS.LOG_ERROR)
            return None

        self.channels = numchannels
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.audio_track:
            self.audio_track.stop()
            self.audio_track.release()

        if self.audio_record:
            self.audio_record.stop()
            self.audio_record.release()

    @property
    def latency(self):
        # TODO: Get actual stream latency via JNI here
        return 0.001

class _Player(_Stream):
    def _connect_stream(self):
        try:
            AudioAttributes = autoclass("android.media.AudioAttributes")
            AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")
            AudioFormat = autoclass("android.media.AudioFormat")
            AudioFormatBuilder = autoclass("android.media.AudioFormat$Builder")
            AudioTrack = autoclass("android.media.AudioTrack")

            aa_builder = AudioAttributesBuilder()
            aa_builder.setUsage(AudioAttributes.USAGE_MEDIA)
            aa_builder.setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            self.audio_attributes = aa_builder.build()

            af_builder = AudioFormatBuilder()
            af_builder.setSampleRate(int(self._samplerate))
            af_builder.setEncoding(self.audio_encoding)
            af_builder.setChannelMask(self.audio_format_out)
            self.audio_format = af_builder.build()

            self.audio_track = AudioTrack(self.audio_attributes, self.audio_format, self.min_buffer_playback, self.audio_track_mode, 0)
            self.audio_track.play()

        except Exception as e:
            RNS.log(f"Error while connecting output audio stream via JNI: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    def play(self, frame):
        if not self.audio_track: return

        input_samples = frame*self.TYPE_MAP_FACTOR
        data = input_samples.astype(numpy.int16)

        if data.ndim == 1:                            data = data[:, None] # Force 2D array
        if data.ndim != 2:                            raise TypeError(f"data must be 1d or 2d, not {data.ndim}d")
        if data.shape[1] == 1 and self.channels != 1: data = numpy.tile(data, [1, self.channels])
        if data.shape[1] != self.channels:            raise TypeError(f"second dimension of data must be equal to the number of channels, not {data.shape[1]}")
        
        while data.nbytes > 0:
            samples_bytes     = data.ravel().tobytes()
            written_bytes     = self.audio_track.write(samples_bytes, 0, len(samples_bytes))
            written_samples   = written_bytes//self.bytes_per_sample
            data = data[written_samples:]
            # TODO: Remove debug
            # if written_bytes != len(samples_bytes): RNS.log(f"Only wrote {written_bytes} of {len(samples_bytes)}, {written_samples} of {data.shape[0]} samples", RNS.LOG_WARNING)
            # else: RNS.log(f"Wrote {written_samples} samples / {written_bytes} bytes")

class _Recorder(_Stream):
    def __init__(self, *args, **kwargs):
        super(_Recorder, self).__init__(*args, **kwargs)
        self.AudioRecord = autoclass("android.media.AudioRecord")
        self._pending_chunk = numpy.zeros((0, ), dtype='float32')

    def _connect_stream(self):
        try:
            AudioSource = autoclass("android.media.MediaRecorder$AudioSource")

            self.audio_record = self.AudioRecord(AudioSource.VOICE_COMMUNICATION, self._samplerate, self.audio_format_in, self.audio_encoding, self.min_buffer_recording)
            self.audio_record.startRecording()

        except Exception as e:
            RNS.log(f"Error while connecting input audio stream via JNI: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    def _record_chunk(self):
        try:
            audio_data = bytearray(self.min_buffer_recording)
            bytes_read = self.audio_record.read(audio_data, 0, self.min_buffer_recording, self.audio_record.READ_NON_BLOCKING)
            if bytes_read == 0: time.sleep(0.005)

            if   bytes_read == self.audio_record.ERROR_INVALID_OPERATION: RNS.log(f"Invalid operation error from JNI on {self}", RNS.LOG_ERROR)
            elif bytes_read == self.audio_record.ERROR_BAD_VALUE:         RNS.log(f"Bad value error from JNI on {self}", RNS.LOG_ERROR)
            else:
                recorded_samples = numpy.frombuffer(audio_data[:bytes_read], dtype="int16")/self.TYPE_MAP_FACTOR
                return recorded_samples.astype("float32")

        except Exception as e:
            RNS.log(f"Error while reading audio chunk: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)
            return None


    def record(self, numframes=None):
        if numframes is None: return numpy.reshape(numpy.concatenate([self.flush().ravel(), self._record_chunk()]), [-1, self.channels])
        else:
            captured_data = [self._pending_chunk]
            captured_frames = self._pending_chunk.shape[0] / self.channels
            if captured_frames >= numframes:
                keep, self._pending_chunk = numpy.split(self._pending_chunk, [int(numframes * self.channels)])
                return numpy.reshape(keep, [-1, self.channels])
            
            else:
                while captured_frames < numframes:
                    chunk = self._record_chunk()
                    captured_data.append(chunk)
                    captured_frames += len(chunk)/self.channels
                
                to_split = int(len(chunk) - (captured_frames - numframes) * self.channels)
                captured_data[-1], self._pending_chunk = numpy.split(captured_data[-1], [to_split])
                return numpy.reshape(numpy.concatenate(captured_data), [-1, self.channels])

    def flush(self):
        last_chunk = numpy.reshape(self._pending_chunk, [-1, self.channels])
        self._pending_chunk = numpy.zeros((0, ), dtype="float32")
        return last_chunk
