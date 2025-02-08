import RNS
from .Sinks import RemoteSink
from .Sources import RemoteSource
from collections import deque
from RNS.vendor import umsgpack as mp

FIELD_SIGNALLING = 0x00
FIELD_FRAMES     = 0x01

class SignallingReceiver():
    def __init__(self, proxy=None):
        self.outgoing_signals = deque()
        self.proxy = proxy

    def handle_signalling_from(self, source):
        source.set_packet_callback(self._packet)

    def signalling_received(self, signals, source):
        if self.proxy: self.proxy.signalling_received(signals, source)

    def signal(self, signal, destination):
        signalling_data = {FIELD_SIGNALLING:[signal]}
        signalling_packet = RNS.Packet(destination, mp.packb(signalling_data), create_receipt=False)
        signalling_packet.send()

    def _packet(self, data, packet, unpacked=None):
        try:
            if not unpacked: unpacked = mp.unpackb(data)
            source = packet.link if hasattr(packet, "link") else None
            if type(unpacked) == dict:
                if FIELD_SIGNALLING in unpacked:
                    signalling = unpacked[FIELD_SIGNALLING]
                    if type(signalling) == list:
                        self.signalling_received(signalling, source)
                    else:
                        self.signalling_received([signalling], source)

        except Exception as e:
            RNS.log(f"{self} could not process incoming packet: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

class Packetizer(RemoteSink):
    def __init__(self, destination):
        self.destination = destination
        self.should_run = False

    def handle_frame(self, frame, source=None):
        if type(self.destination) == RNS.Link and not self.destination.status == RNS.Link.ACTIVE:
            return

        packet_data = {FIELD_FRAMES:frame}
        frame_packet = RNS.Packet(self.destination, mp.packb(packet_data), create_receipt=False)
        frame_packet.send()

    def start(self):
        if not self.should_run:
            RNS.log(f"{self} starting", RNS.LOG_DEBUG)
            self.should_run = True

    def stop(self):
        self.should_run = False

class LinkSource(RemoteSource, SignallingReceiver):
    def __init__(self, link, signalling_receiver):
        self.should_run = False
        self.link       = link
        self.proxy      = signalling_receiver
        self.link.set_packet_callback(self._packet)

    def _packet(self, data, packet):
        try:
            unpacked = mp.unpackb(data)
            if type(unpacked) == dict:
                if FIELD_FRAMES in unpacked:
                    frames = unpacked[FIELD_FRAMES]
                    if type(frames) != list: frames = [frames]
                    for frame in frames:
                        if self.codec and self.sink:
                            self.sink.handle_frame(self.codec.decode(frame), self)

                if FIELD_SIGNALLING in unpacked:
                    super()._packet(data=None, packet=packet, unpacked=unpacked)

        except Exception as e:
            RNS.log(f"{self} could not process incoming packet: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    def start(self):
        if not self.should_run:
            RNS.log(f"{self} starting", RNS.LOG_DEBUG)
            self.should_run = True

    def stop(self):
        self.should_run = False