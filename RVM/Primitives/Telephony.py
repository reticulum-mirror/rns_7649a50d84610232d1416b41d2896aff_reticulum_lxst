import RNS
import RVM
import time
import threading

from RVM import APP_NAME
from RVM import Mixer, Pipeline
from RVM.Codecs import Raw, Opus, Codec2
from RVM.Sinks import LineSink
from RVM.Sources import LineSource
from RVM.Network import Packetizer, LinkSource
from RNS.vendor import umsgpack as mp

PRIMITIVE_NAME = "telephony"

class Signalling():
    STATUS_BUSY        = 0x00
    STATUS_REJECTED    = 0x01
    STATUS_AVAILABLE   = 0x02
    STATUS_RINGING     = 0x03
    STATUS_CONNECTING  = 0x04
    STATUS_ESTABLISHED = 0x05

class Telephone():
    RING_TIME        = 30

    def __init__(self, identity, ring_time=RING_TIME):
        # if not isinstance(identity, RNS.Identity): raise TypeError("Invalid identity")
        self.identity = identity
        self.destination = RNS.Destination(self.identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, PRIMITIVE_NAME)
        self.destination.set_link_established_callback(self.__incoming_link_established)
        self.call_handler_lock = threading.Lock()
        self.links = {}
        self.ring_time = ring_time
        self.active_call = None
        self.__ringing_callback = None
        self.codec = None
        self.audio_output = None
        self.audio_input = None
        self.local_mixer = None
        self.remote_mixer = None
        self.transmit_pipeline = None
        self.target_frame_time_ms = None

        self.announce()
        RNS.log(f"{self} listening on {RNS.prettyhexrep(self.destination.hash)}", RNS.LOG_DEBUG)

    def announce(self):
        self.destination.announce()

    def set_ringing_callback(self, callback):
        if not callable(callback): raise TypeError(f"Invalid callback, {callback} is not callable")
        self.__ringing_callback = callback

    def __incoming_link_established(self, link):
        link.is_incoming = True
        link.is_outgoing = False
        with self.call_handler_lock:
            if self.active_call:
                self.signal(Signalling.STATUS_BUSY, link)
                link.teardown()
            else:
                link.set_remote_identified_callback(self.__caller_identified)
                self.links[link.link_id] = link
                self.signal(Signalling.STATUS_AVAILABLE, link)

    def __caller_identified(self, link, identity):
        with self.call_handler_lock:
            RNS.log(f"Caller identified as {RNS.prettyhexrep(identity.hash)}, ringing", RNS.LOG_DEBUG)
            if self.active_call:
                self.__signal(Signalling.STATUS_BUSY, link)
                link.teardown()
            else:
                self.active_call = link
                self.signal(Signalling.STATUS_RINGING, self.active_call)
                if callable(self.__ringing_callback):
                    self.__ringing_callback(identity)

    def signal(self, signal, link):
        RNS.log(f"Signalling {signal}")
        signalling_data = [signal]
        signalling_packet = RNS.Packet(link, mp.packb(signalling_data), create_receipt=False)
        signalling_packet.send()

    def answer(self, identity):
        with self.call_handler_lock:
            if not self.active_call:
                RNS.log(f"Answering call failed, no active incoming call", RNS.LOG_ERROR)
                return False
            elif not self.active_call.remote_identity:
                RNS.log(f"Answering call failed, active incoming call is not from {RNS.prettyhexrep(identity)}", RNS.LOG_ERROR)
                return False
            else:
                RNS.log(f"Answering call from {RNS.prettyhexrep(identity)}", RNS.LOG_DEBUG)
                self.__open_pipelines(identity)
                RNS.log(f"Call setup complete for {RNS.prettyhexrep(identity)}")
                return True

    def hangup(self):
        self.__stop_pipelines()
        if self.active_call:
            self.active_call.teardown()

    def select_codec(self):
        self.codec = Opus(profile=Opus.PROFILE_VOICE_MEDIUM)
        return self.codec

    def select_target_frame_time(self):
        self.target_frame_time_ms = 40
        return self.target_frame_time_ms

    def __open_pipelines(self, identity):
        if not self.active_call.remote_identity == identity:
            RNS.log("Identity mismatch while opening call pipelines, tearing down call", RNS.LOG_ERROR)
            self.hangup()
        else:
            RNS.log(f"Opening audio pipelines for call with {RNS.prettyhexrep(identity)}")
            self.signal(Signalling.STATUS_CONNECTING, self.active_call)
            self.select_target_frame_time()
            self.select_codec()
            self.remote_mixer = Mixer(target_frame_ms=self.target_frame_time_ms)
            self.audio_input = LineSource(target_frame_ms=self.target_frame_time_ms, codec=raw, sink=remote_mixer)
            self.audio_output = LineSink()
            self.transmit_pipeline = RVM.Pipeline(source=self.remote_mixer, codec=self.codec, sink=Packetizer(self.active_call))
            self.receive_pipeline = RVM.Pipeline(source=LinkSource(self.active_call), codec=self.codec, sink=self.audio_output)
            self.signal(Signalling.STATUS_ESTABLISHED, self.active_call)
            self.__start_pipelines()

    def __start_pipelines(self):
        pass

    def __stop_pipelines(self):
        pass

    def call(self, identity):
        with self.call_handler_lock:
            if not self.active_call:
                call_destination = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, PRIMITIVE_NAME)
                if not RNS.Transport.has_path(call_destination.hash):
                    RNS.log(f"No path known for call to {RNS.prettyhexrep(call_destination.hash)}, requesting path...", RNS.LOG_DEBUG)
                    RNS.Transport.request_path(call_destination.hash)
                    while not RNS.Transport.has_path(call_destination.hash):
                        # TODO: Add timeout
                        time.sleep(0.2)

                RNS.log(f"Establishing link with {RNS.prettyhexrep(call_destination.hash)}...", RNS.LOG_DEBUG)
                self.active_call = RNS.Link(call_destination,
                                            established_callback=self.__outgoing_link_established,
                                            closed_callback=self.__outgoing_link_closed)
                
                self.active_call.is_incoming = False
                self.active_call.is_outgoing = True

    def __outgoing_link_established(self, link):
        RNS.log(f"Link established for call with {link.get_remote_identity()}", RNS.LOG_DEBUG)
        link.set_packet_callback(self.__packet)

    def __outgoing_link_closed(self, link):
        pass

    def __packet(self, data, packet):
        RNS.log("Got packet")
        message = mp.unpackb(data)
        if packet.link != self.active_call:
            RNS.log("Received packet on non-active call, ignoring", RNS.LOG_DEBUG)
        else:
            if message[0] == Signalling.STATUS_BUSY:
                RNS.log("Remote is busy, terminating", RNS.LOG_DEBUG)
                self.hangup()
            elif message[0] == Signalling.STATUS_REJECTED:
                RNS.log("Remote rejected call, terminating", RNS.LOG_DEBUG)
                self.hangup()
            elif message[0] == Signalling.STATUS_AVAILABLE:
                RNS.log("Line available, sending identification", RNS.LOG_DEBUG)
                packet.link.identify(self.identity)
            elif message[0] == Signalling.STATUS_RINGING:
                RNS.log("Identification accepted, remote is now ringing", RNS.LOG_DEBUG)
            elif message[0] == Signalling.STATUS_CONNECTING:
                RNS.log("Call answered, remote is performing call setup, opening audio pipelines")
                self.__open_pipelines(self.active_call.remote_identity)
            elif message[0] == Signalling.STATUS_ESTABLISHED:
                RNS.log("Remote call setup completed, starting audio pipelines")
                self.start_pipelines()

if __name__ == "__main__":
    RNS.Reticulum()
    i = RNS.Identity()
    t = Telephone(i)
    cd = input()
    dh = bytes.fromhex(cd)
    RNS.Transport.request_path(dh)
    while not RNS.Transport.has_path(dh):
        RNS.log("Waiting for path...")
        time.sleep(1)

    rid = RNS.Identity.recall(dh)
    if not rid:
        RNS.log("Could not recall id")
        exit()
    else:
        RNS.log(f"Calling {rid}")
        t.call(rid)

        input()
        t.hangup()
        time.sleep(1)