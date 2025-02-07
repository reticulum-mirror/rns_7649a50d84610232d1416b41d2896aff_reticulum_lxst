import RNS
from .Sinks import RemoteSink
from .Sources import RemoteSource

class Packetizer(RemoteSink):
    def __init__(self, destination):
        self.destination = destination
        self.should_run = False

    def start(self):
        if not self.should_run:
            RNS.log(f"{self} starting", RNS.LOG_DEBUG)
            self.should_run = True

    def stop(self):
        self.should_run = False

class LinkSource(RemoteSource):
    def __init__(self, link, signalling_packet_handler):
        self.should_run = False
        self.link = link
        self.signalling_packet_handler = signalling_packet_handler

    def start(self):
        if not self.should_run:
            RNS.log(f"{self} starting", RNS.LOG_DEBUG)
            self.should_run = True

    def stop(self):
        self.should_run = False