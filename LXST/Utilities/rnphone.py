#!/usr/bin/env python3

import RNS
import os
import sys
import time
import argparse

from LXST._version import __version__
from LXST.Primitives.Telephony import Telephone

class ReticulumTelephone():
    STATE_AVAILABLE = 0x00
    STATE_RINGING   = 0x01
    STATE_IN_CALL   = 0x02

    def __init__(self, configdir, rnsconfigdir, verbosity = 0):
        self.should_run = False
        self.state      = self.STATE_AVAILABLE
        
        reticulum       = RNS.Reticulum(configdir=rnsconfigdir, loglevel=3+verbosity)        
        self.telephone  = Telephone(RNS.Identity())
        self.telephone.set_ringing_callback(self.ringing)
        self.telephone.set_ended_callback(self.call_ended)

    @property
    def is_available(self):
        return self.state == self.STATE_AVAILABLE

    @property
    def is_in_call(self):
        return self.state == self.STATE_IN_CALL

    @property
    def is_ringing(self):
        return self.state == self.STATE_RINGING

    def start(self):
        if not self.should_run:
            self.should_run = True
            self.run()

    def stop(self):
        self.should_run = False

    def ringing(self, remote_identity):
        self.state = self.STATE_RINGING
        self.caller  = remote_identity
        print(f"Incoming call from {RNS.prettyhexrep(self.caller.hash)}")

    def call_ended(self, remote_identity):
        if self.is_in_call or self.is_ringing:
            self.state = self.STATE_AVAILABLE
            print(f"Call with {RNS.prettyhexrep(self.caller.hash)} ended")

    def run(self):
        global telephone
        while self.should_run:
            input()
            if self.is_ringing:
                if self.telephone.answer(self.caller):
                    self.state = self.STATE_IN_CALL
                    print(f"Answered call from {RNS.prettyhexrep(self.caller.hash)}")
                else:
                    print(f"Could not answer call from {RNS.prettyhexrep(self.caller.hash)}")

            elif self.is_in_call:
                print(f"Hanging up call with {RNS.prettyhexrep(self.caller.hash)}")
                self.telephone.hangup()

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Telephone Utility")

        parser.add_argument("--config", action="store", default=None, help="path to config directory", type=str)
        parser.add_argument("--rnsconfig", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument("--version", action="version", version="rnprobe {version}".format(version=__version__))
        parser.add_argument('-v', '--verbose', action='count', default=0)

        args = parser.parse_args()

        ReticulumTelephone(configdir = args.config,
                           rnsconfigdir = args.rnsconfig,
                           verbosity = args.verbose).start()

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()