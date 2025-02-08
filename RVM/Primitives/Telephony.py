import RNS
import RVM
import time
import threading

from RVM import APP_NAME
from RVM import Mixer, Pipeline
from RVM.Codecs import Raw, Opus, Codec2
from RVM.Sinks import LineSink
from RVM.Sources import LineSource
from RVM.Network import SignallingReceiver, Packetizer, LinkSource

PRIMITIVE_NAME = "telephony"

class Signalling():
    STATUS_BUSY        = 0x00
    STATUS_REJECTED    = 0x01
    STATUS_AVAILABLE   = 0x02
    STATUS_RINGING     = 0x03
    STATUS_CONNECTING  = 0x04
    STATUS_ESTABLISHED = 0x05
    CALL_STATUS_CODES  = [STATUS_BUSY, STATUS_REJECTED, STATUS_AVAILABLE,
                          STATUS_RINGING, STATUS_CONNECTING, STATUS_ESTABLISHED]

class Telephone(SignallingReceiver):
    RING_TIME          = 30

    def __init__(self, identity, ring_time=RING_TIME, auto_answer=None):
        super().__init__()
        # if not isinstance(identity, RNS.Identity): raise TypeError("Invalid identity")
        self.identity = identity
        self.destination = RNS.Destination(self.identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, PRIMITIVE_NAME)
        self.destination.set_proof_strategy(RNS.Destination.PROVE_NONE)
        self.destination.set_link_established_callback(self.__incoming_link_established)
        self.call_handler_lock = threading.Lock()
        self.pipeline_lock = threading.Lock()
        self.links = {}
        self.ring_time = ring_time
        self.auto_answer = auto_answer
        self.active_call = None
        self.__ringing_callback = None
        self.audio_output = None
        self.audio_input = None
        self.transmit_codec = None
        self.receive_codec = None
        self.local_mixer = None
        self.remote_mixer = None
        self.receive_pipeline = None
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
                link.set_link_closed_callback(self.__link_closed)
                self.links[link.link_id] = link
                self.signal(Signalling.STATUS_AVAILABLE, link)

    def __caller_identified(self, link, identity):
        with self.call_handler_lock:
            if self.active_call:
                RNS.log(f"Caller identified as {RNS.prettyhexrep(identity.hash)}, but line is already active, signalling busy", RNS.LOG_DEBUG)
                self.__signal(Signalling.STATUS_BUSY, link)
                link.teardown()
            else:
                RNS.log(f"Caller identified as {RNS.prettyhexrep(identity.hash)}, ringing", RNS.LOG_DEBUG)
                self.active_call = link
                self.signal(Signalling.STATUS_RINGING, self.active_call)
                if callable(self.__ringing_callback):
                    self.__ringing_callback(identity)
                if self.auto_answer:
                    def cb():
                        RNS.log(f"Auto-answering call from {RNS.prettyhexrep(identity.hash)} in {RNS.prettytime(self.auto_answer)}", RNS.LOG_DEBUG)
                        time.sleep(self.auto_answer)
                        self.answer(identity)
                    threading.Thread(target=cb, daemon=True).start()

    def __link_closed(self, link):
        if link == self.active_call:
            RNS.log(f"Remote for {RNS.prettyhexrep(link.get_remote_identity().hash)} hung up")
            self.hangup()

    def signal(self, signal, link):
        RNS.log(f"{self} signalling {signal}")
        if signal in Signalling.CALL_STATUS_CODES: self.call_status = signal
        super().signal(signal, link)

    def answer(self, identity):
        with self.call_handler_lock:
            if self.active_call and self.active_call.get_remote_identity() == identity and self.call_status > Signalling.STATUS_RINGING:
                RNS.log(f"Incoming call from {identity.hash} already answered and active")
                return False
            elif not self.active_call:
                RNS.log(f"Answering call failed, no active incoming call", RNS.LOG_ERROR)
                return False
            elif not self.active_call.get_remote_identity():
                RNS.log(f"Answering call failed, active incoming call is not from {RNS.prettyhexrep(identity.hash)}", RNS.LOG_ERROR)
                return False
            else:
                RNS.log(f"Answering call from {RNS.prettyhexrep(identity.hash)}", RNS.LOG_DEBUG)
                self.__open_pipelines(identity)
                self.__start_pipelines()
                RNS.log(f"Call setup complete for {RNS.prettyhexrep(identity.hash)}")
                return True

    def hangup(self):
        self.__stop_pipelines()
        self.remote_mixer = None
        self.receive_pipeline = None
        self.transmit_pipeline = None
        if self.active_call:
            remote_identity = self.active_call.get_remote_identity()
            if self.active_call.status == RNS.Link.ACTIVE: self.active_call.teardown()
            self.active_call = None
            RNS.log(f"Call with {RNS.prettyhexrep(remote_identity.hash)} terminated", RNS.LOG_DEBUG)

    def select_codec(self):
        self.transmit_codec = Opus(profile=Opus.PROFILE_VOICE_MEDIUM)
        self.receive_codec = Opus(profile=Opus.PROFILE_VOICE_MEDIUM)

        # TODO: Remove debug
        # self.transmit_codec = Opus(profile=Opus.PROFILE_AUDIO_HIGH)
        # self.receive_codec = Opus(profile=Opus.PROFILE_AUDIO_HIGH)
        # self.transmit_codec = Codec2(mode=Codec2.CODEC2_3200)
        # self.receive_codec = Codec2(mode=Codec2.CODEC2_3200)

    def select_target_frame_time(self):
        self.target_frame_time_ms = 40
        return self.target_frame_time_ms

    def __open_pipelines(self, identity):
        with self.pipeline_lock:
            if not self.active_call.get_remote_identity() == identity:
                RNS.log("Identity mismatch while opening call pipelines, tearing down call", RNS.LOG_ERROR)
                self.hangup()
            else:
                if not hasattr(self.active_call, "pipelines_opened"): self.active_call.pipelines_opened = False
                if self.active_call.pipelines_opened:
                    RNS.log(f"Pipelines already openened for call with {RNS.prettyhexrep(identity.hash)}", RNS.LOG_ERROR)
                else:
                    RNS.log(f"Opening audio pipelines for call with {RNS.prettyhexrep(identity.hash)}")
                    if self.active_call.is_incoming: self.signal(Signalling.STATUS_CONNECTING, self.active_call)
                    self.select_target_frame_time()
                    self.select_codec()
                    link_source = LinkSource(link=self.active_call, signalling_receiver=self)
                    self.remote_mixer = Mixer(target_frame_ms=self.target_frame_time_ms)
                    self.audio_input = LineSource(target_frame_ms=self.target_frame_time_ms, codec=Raw(), sink=self.remote_mixer)
                    # self.audio_input = LineSource(target_frame_ms=self.target_frame_time_ms)
                    self.audio_output = LineSink()
                    self.transmit_pipeline = RVM.Pipeline(source=self.remote_mixer, codec=self.transmit_codec, sink=Packetizer(self.active_call))
                    # self.transmit_pipeline = RVM.Pipeline(source=self.audio_input, codec=self.transmit_codec, sink=Packetizer(self.active_call))
                    self.receive_pipeline = RVM.Pipeline(source=link_source, codec=self.receive_codec, sink=self.audio_output)
                    self.signal(Signalling.STATUS_ESTABLISHED, self.active_call)

    def __start_pipelines(self):
        with self.pipeline_lock:
            if self.remote_mixer:      self.remote_mixer.start()
            # if self.audio_input:       self.audio_input.start()

            # TODO: Remove debug ###################################
            if self.active_call.is_incoming:
                if self.audio_input:       self.audio_input.start()
            ########################################################
            
            if self.transmit_pipeline: self.transmit_pipeline.start()
            RNS.log(f"Audio pipelines started", RNS.LOG_DEBUG)

    def __stop_pipelines(self):
        with self.pipeline_lock:
            if self.remote_mixer:      self.remote_mixer.stop()
            if self.audio_input:       self.audio_input.stop()
            if self.receive_pipeline:  self.receive_pipeline.stop()
            if self.transmit_pipeline: self.transmit_pipeline.stop()
            RNS.log(f"Audio pipelines stopped", RNS.LOG_DEBUG)

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
        self.handle_signalling_from(link)

    def __outgoing_link_closed(self, link):
        pass

    def signalling_received(self, signals, source):
        for signal in signals:
            if source != self.active_call:
                RNS.log("Received signalling on non-active call, ignoring", RNS.LOG_DEBUG)
            else:
                if signal == Signalling.STATUS_BUSY:
                    RNS.log("Remote is busy, terminating", RNS.LOG_DEBUG)
                    self.hangup()
                elif signal == Signalling.STATUS_REJECTED:
                    RNS.log("Remote rejected call, terminating", RNS.LOG_DEBUG)
                    self.hangup()
                elif signal == Signalling.STATUS_AVAILABLE:
                    RNS.log("Line available, sending identification", RNS.LOG_DEBUG)
                    source.identify(self.identity)
                elif signal == Signalling.STATUS_RINGING:
                    RNS.log("Identification accepted, remote is now ringing", RNS.LOG_DEBUG)
                elif signal == Signalling.STATUS_CONNECTING:
                    RNS.log("Call answered, remote is performing call setup, opening audio pipelines", RNS.LOG_DEBUG)
                    self.__open_pipelines(self.active_call.get_remote_identity())
                elif signal == Signalling.STATUS_ESTABLISHED:
                    RNS.log("Remote call setup completed, starting audio pipelines", RNS.LOG_DEBUG)
                    self.__start_pipelines()
                    RNS.log(f"Call setup complete for {RNS.prettyhexrep(self.active_call.get_remote_identity().hash)}", RNS.LOG_DEBUG)

# TODO: Remove debug
if __name__ == "__main__":
    RNS.Reticulum()
    i = RNS.Identity()
    t = Telephone(i, auto_answer=1)
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
        RNS.log("Hanging up")
        t.hangup()
        time.sleep(1)