import RNS
import LXST
import time
import threading

from LXST import APP_NAME
from LXST import Mixer, Pipeline
from LXST.Codecs import Raw, Opus, Codec2, Null
from LXST.Sinks import LineSink
from LXST.Sources import LineSource
from LXST.Generators import ToneSource
from LXST.Network import SignallingReceiver, Packetizer, LinkSource

PRIMITIVE_NAME = "telephony"

class Signalling():
    STATUS_BUSY        = 0x00
    STATUS_REJECTED    = 0x01
    STATUS_CALLING     = 0x02
    STATUS_AVAILABLE   = 0x03
    STATUS_RINGING     = 0x04
    STATUS_CONNECTING  = 0x05
    STATUS_ESTABLISHED = 0x06
    CALL_STATUS_CODES  = [STATUS_BUSY, STATUS_REJECTED, STATUS_CALLING, STATUS_AVAILABLE,
                          STATUS_RINGING, STATUS_CONNECTING, STATUS_ESTABLISHED]

class Telephone(SignallingReceiver):
    RING_TIME          = 30
    WAIT_TIME          = 30

    def __init__(self, identity, ring_time=RING_TIME, wait_time=WAIT_TIME, auto_answer=None):
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
        self.wait_time = wait_time
        self.auto_answer = auto_answer
        self.active_call = None
        self.call_status = None
        self.__ringing_callback = None
        self.__established_callback = None
        self.__ended_callback = None
        self.audio_output = None
        self.audio_input = None
        self.dial_tone = None
        self.transmit_codec = None
        self.receive_codec = None
        self.receive_mixer = None
        self.transmit_mixer = None
        self.receive_pipeline = None
        self.transmit_pipeline = None
        self.target_frame_time_ms = None

        self.announce()
        RNS.log(f"{self} listening on {RNS.prettyhexrep(self.destination.hash)}", RNS.LOG_DEBUG)

    def announce(self):
        def job():
            time.sleep(1)
            self.destination.announce()
        threading.Thread(target=job, daemon=True).start()

    def set_ringing_callback(self, callback):
        if not callable(callback): raise TypeError(f"Invalid callback, {callback} is not callable")
        self.__ringing_callback = callback

    def set_established_callback(self, callback):
        if not callable(callback): raise TypeError(f"Invalid callback, {callback} is not callable")
        self.__established_callback = callback

    def set_ended_callback(self, callback):
        if not callable(callback): raise TypeError(f"Invalid callback, {callback} is not callable")
        self.__ended_callback = callback

    def __timeout_incoming_call_at(self, call, timeout):
        def job():
            while time.time()<timeout and self.active_call == call:
                time.sleep(0.25)

            if self.active_call == call and self.call_status < Signalling.STATUS_ESTABLISHED:
                RNS.log(f"Ring timeout on call from {RNS.prettyhexrep(self.active_call.hash)}, hanging up", RNS.LOG_DEBUG)
                self.hangup()

        threading.Thread(target=job, daemon=True).start()

    def __timeout_outgoing_call_at(self, call, timeout):
        def job():
            while time.time()<timeout and self.active_call == call:
                time.sleep(0.25)

            if self.active_call == call and self.call_status < Signalling.STATUS_ESTABLISHED:
                RNS.log(f"Timeout on outgoing call to {RNS.prettyhexrep(self.active_call.hash)}, hanging up", RNS.LOG_DEBUG)
                self.hangup()

        threading.Thread(target=job, daemon=True).start()

    def __incoming_link_established(self, link):
        link.is_incoming = True
        link.is_outgoing = False
        with self.call_handler_lock:
            if self.active_call:
                RNS.log(f"Incoming call, but already in-call with {RNS.prettyhexrep(self.active_call.hash)}, signalling busy", RNS.LOG_DEBUG)
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
                if callable(self.__ringing_callback): self.__ringing_callback(identity)
                if self.auto_answer:
                    def cb():
                        RNS.log(f"Auto-answering call from {RNS.prettyhexrep(identity.hash)} in {RNS.prettytime(self.auto_answer)}", RNS.LOG_DEBUG)
                        time.sleep(self.auto_answer)
                        self.answer(identity)
                    threading.Thread(target=cb, daemon=True).start()
                
                else:
                    self.__timeout_incoming_call_at(self.active_call, time.time()+self.ring_time)

    def __link_closed(self, link):
        if link == self.active_call:
            RNS.log(f"Remote for {RNS.prettyhexrep(link.get_remote_identity().hash)} hung up", RNS.LOG_DEBUG)
            self.hangup()

    def signal(self, signal, link):
        if signal in Signalling.CALL_STATUS_CODES: self.call_status = signal
        super().signal(signal, link)

    def answer(self, identity):
        with self.call_handler_lock:
            if self.active_call and self.active_call.get_remote_identity() == identity and self.call_status > Signalling.STATUS_RINGING:
                RNS.log(f"Incoming call from {RNS.prettyhexrep(identity.hash)} already answered and active")
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
                RNS.log(f"Call setup complete for {RNS.prettyhexrep(identity.hash)}", RNS.LOG_DEBUG)
                if callable(self.__established_callback): self.__established_callback(self.active_call.get_remote_identity())
                return True

    def hangup(self):
        if self.active_call:
            with self.call_handler_lock:
                terminating_call = self.active_call; self.active_call = None
                remote_identity = terminating_call.get_remote_identity()
                if terminating_call.status == RNS.Link.ACTIVE:
                    terminating_call.teardown()
                self.__stop_pipelines()
                self.transmit_mixer = None
                self.receive_pipeline = None
                self.transmit_pipeline = None
                if remote_identity:
                    RNS.log(f"Call with {RNS.prettyhexrep(remote_identity.hash)} terminated", RNS.LOG_DEBUG)
                else:
                    RNS.log(f"Outgoing call could not be connected, link establishment failed", RNS.LOG_DEBUG)
        
            if callable(self.__ended_callback): self.__ended_callback(remote_identity)

    def select_call_codecs(self):
        self.transmit_codec = Opus(profile=Opus.PROFILE_VOICE_MEDIUM)
        self.receive_codec = Null()

    def select_call_frame_time(self):
        self.target_frame_time_ms = 60
        return self.target_frame_time_ms

    def __prepare_dialling_pipelines(self):
        self.select_call_frame_time()
        self.select_call_codecs()
        if self.audio_output == None:     self.audio_output = LineSink()
        if self.receive_mixer == None:    self.receive_mixer = Mixer(target_frame_ms=self.target_frame_time_ms)
        if self.dial_tone == None:        self.dial_tone = ToneSource(frequency=388, ease_time_ms=3.14159, target_frame_ms=self.target_frame_time_ms, codec=Null(), sink=self.receive_mixer)
        if self.receive_pipeline == None: self.receive_pipeline = LXST.Pipeline(source=self.receive_mixer, codec=Null(), sink=self.audio_output)

    def __enable_dial_tone(self):
        if not self.receive_mixer.should_run: self.receive_mixer.start()
        self.dial_tone.start()
    
    def __disable_dial_tone(self):
        self.dial_tone.stop()

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
                    RNS.log(f"Opening audio pipelines for call with {RNS.prettyhexrep(identity.hash)}", RNS.LOG_DEBUG)
                    if self.active_call.is_incoming: self.signal(Signalling.STATUS_CONNECTING, self.active_call)

                    self.__prepare_dialling_pipelines()
                    self.transmit_mixer = Mixer(target_frame_ms=self.target_frame_time_ms)
                    self.audio_input = LineSource(target_frame_ms=self.target_frame_time_ms, codec=Raw(), sink=self.transmit_mixer)
                    self.transmit_pipeline = LXST.Pipeline(source=self.transmit_mixer,
                                                          codec=self.transmit_codec,
                                                          sink=Packetizer(self.active_call, failure_callback=self.__packetizer_failure))
                    
                    self.active_call.audio_source = LinkSource(link=self.active_call, signalling_receiver=self, sink=self.receive_mixer)
                    
                    self.signal(Signalling.STATUS_ESTABLISHED, self.active_call)

    def __packetizer_failure(self):
        RNS.log(f"Frame packetization failed, terminating call", RNS.LOG_ERROR)
        self.hangup()

    def __start_pipelines(self):
        with self.pipeline_lock:
            if self.receive_mixer:     self.receive_mixer.start()
            if self.transmit_mixer:    self.transmit_mixer.start()
            if self.audio_input:       self.audio_input.start()
            if self.transmit_pipeline: self.transmit_pipeline.start()
            RNS.log(f"Audio pipelines started", RNS.LOG_DEBUG)

    def __stop_pipelines(self):
        with self.pipeline_lock:
            if self.receive_mixer:     self.receive_mixer.stop()
            if self.transmit_mixer:    self.transmit_mixer.stop()
            if self.audio_input:       self.audio_input.stop()
            if self.receive_pipeline:  self.receive_pipeline.stop()
            if self.transmit_pipeline: self.transmit_pipeline.stop()
            RNS.log(f"Audio pipelines stopped", RNS.LOG_DEBUG)

    def call(self, identity):
        with self.call_handler_lock:
            if not self.active_call:
                outgoing_call_timeout = time.time()+self.wait_time
                call_destination = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, PRIMITIVE_NAME)
                if not RNS.Transport.has_path(call_destination.hash):
                    RNS.log(f"No path known for call to {RNS.prettyhexrep(call_destination.hash)}, requesting path...", RNS.LOG_DEBUG)
                    RNS.Transport.request_path(call_destination.hash)
                    while not RNS.Transport.has_path(call_destination.hash) and time.time() < outgoing_call_timeout: time.sleep(0.2)
                
                if not RNS.Transport.has_path(call_destination.hash) and time.time() >= outgoing_call_timeout:
                    self.hangup()
                else:
                    RNS.log(f"Establishing link with {RNS.prettyhexrep(call_destination.hash)}...", RNS.LOG_DEBUG)
                    self.active_call = RNS.Link(call_destination,
                                                established_callback=self.__outgoing_link_established,
                                                closed_callback=self.__outgoing_link_closed)
                    
                    self.active_call.is_incoming = False
                    self.active_call.is_outgoing = True
                    self.call_status = Signalling.STATUS_CALLING
                    self.__timeout_outgoing_call_at(self.active_call, outgoing_call_timeout)

    def __outgoing_link_established(self, link):
        RNS.log(f"Link established for call with {link.get_remote_identity()}", RNS.LOG_DEBUG)
        link.set_link_closed_callback(self.__link_closed)
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
                    self.__disable_dial_tone()
                    self.hangup()
                elif signal == Signalling.STATUS_REJECTED:
                    RNS.log("Remote rejected call, terminating", RNS.LOG_DEBUG)
                    self.__disable_dial_tone()
                    self.hangup()
                elif signal == Signalling.STATUS_AVAILABLE:
                    RNS.log("Line available, sending identification", RNS.LOG_DEBUG)
                    self.call_status = signal
                    source.identify(self.identity)
                elif signal == Signalling.STATUS_RINGING:
                    RNS.log("Identification accepted, remote is now ringing", RNS.LOG_DEBUG)
                    self.call_status = signal
                    self.__prepare_dialling_pipelines()
                    if self.active_call and self.active_call.is_outgoing:
                        self.__enable_dial_tone()
                elif signal == Signalling.STATUS_CONNECTING:
                    RNS.log("Call answered, remote is performing call setup, opening audio pipelines", RNS.LOG_DEBUG)
                    self.call_status = signal
                    self.__open_pipelines(self.active_call.get_remote_identity())
                    self.__disable_dial_tone()
                elif signal == Signalling.STATUS_ESTABLISHED:
                    if self.active_call and self.active_call.is_outgoing:
                        RNS.log("Remote call setup completed, starting audio pipelines", RNS.LOG_DEBUG)
                        self.__start_pipelines()
                        self.__disable_dial_tone()
                        RNS.log(f"Call setup complete for {RNS.prettyhexrep(self.active_call.get_remote_identity().hash)}", RNS.LOG_DEBUG)
                        self.call_status = signal
                        if callable(self.__established_callback): self.__established_callback(self.active_call.get_remote_identity())
