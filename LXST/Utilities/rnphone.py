#!/usr/bin/env python3

import RNS
import os
import sys
import time
import threading
import argparse

from LXST._version import __version__
from LXST.Primitives.Telephony import Telephone
from RNS.vendor.configobj import ConfigObj

class ReticulumTelephone():
    STATE_AVAILABLE  = 0x00
    STATE_CONNECTING = 0x01
    STATE_RINGING    = 0x02
    STATE_IN_CALL    = 0x03

    RING_TIME        = 30
    WAIT_TIME        = 60
    PATH_TIME        = 10

    def __init__(self, configdir, rnsconfigdir, verbosity = 0):
        self.configdir    = configdir
        self.should_run   = False
        self.state        = self.STATE_AVAILABLE
        self.direction    = None
        self.last_input   = None
        self.first_run    = False
        self.reload_config()
        self.main_menu()
        
        reticulum       = RNS.Reticulum(configdir=rnsconfigdir, loglevel=3+verbosity)
        self.telephone  = Telephone(self.identity, ring_time=self.ring_time, wait_time=self.wait_time)
        self.telephone.set_ringing_callback(self.ringing)
        self.telephone.set_established_callback(self.call_established)
        self.telephone.set_ended_callback(self.call_ended)

    def create_default_config(self):
        rnphone_config = ConfigObj(__default_rnphone_config__.splitlines())
        rnphone_config.filename = self.configpath
        rnphone_config.write()

    def reload_config(self):
        # Get configuration
        if self.configdir == None:
            if os.path.isdir("/etc/rnphone") and os.path.isfile("/etc/rnphone/config"):
                self.configdir = "/etc/rnphone"
            elif os.path.isdir(RNS.Reticulum.userdir+"/.config/rnphone") and os.path.isfile(Reticulum.userdir+"/.config/rnphone/config"):
                self.configdir = RNS.Reticulum.userdir+"/.config/rnphone"
            else:
                self.configdir = RNS.Reticulum.userdir+"/.rnphone"

        self.configpath   = self.configdir+"/config"
        self.ignoredpath  = self.configdir+"/ignored"
        self.allowedpath  = self.configdir+"/allowed"
        self.identitypath = self.configdir+"/identity"
        self.storagedir   = self.configdir+"/storage"

        self.ring_time    = ReticulumTelephone.RING_TIME
        self.wait_time    = ReticulumTelephone.WAIT_TIME
        self.path_time    = ReticulumTelephone.PATH_TIME

        if not os.path.isdir(self.storagedir):
            os.makedirs(self.storagedir)

        if not os.path.isfile(self.configpath):
            self.create_default_config()
            self.first_run = True

        if os.path.isfile(self.configpath):
            try:
                rnphone_config = ConfigObj(self.configpath)
            except Exception as e:
                RNS.log("Could not parse the configuration at "+self.configpath, RNS.LOG_ERROR)
                RNS.log("Check your configuration file for errors!", RNS.LOG_ERROR)
                RNS.panic()

        self.apply_config()

        # Generate or load primary identity
        if os.path.isfile(self.identitypath):
            try:
                self.identity = RNS.Identity.from_file(self.identitypath)
                if self.identity != None:
                    pass
                else:
                    RNS.log("Could not load the Primary Identity from "+self.identitypath, RNS.LOG_ERROR)
                    exit(1)
            except Exception as e:
                RNS.log("Could not load the Primary Identity from "+self.identitypath, RNS.LOG_ERROR)
                RNS.log("The contained exception was: %s" % (str(e)), RNS.LOG_ERROR)
                exit(1)
        else:
            try:
                print("No primary identity file found, creating new...")
                self.identity = RNS.Identity()
                self.identity.to_file(self.identitypath)
                print("Created new Primary Identity %s" % (str(self.identity)))
            except Exception as e:
                RNS.log("Could not create and save a new Primary Identity", RNS.LOG_ERROR)
                RNS.log("The contained exception was: %s" % (str(e)), RNS.LOG_ERROR)
                exit(1)

    def apply_config(self):
        pass

    @property
    def is_available(self):
        return self.state == self.STATE_AVAILABLE

    @property
    def is_in_call(self):
        return self.state == self.STATE_IN_CALL

    @property
    def is_ringing(self):
        return self.state == self.STATE_RINGING

    @property
    def call_is_connecting(self):
        return self.state == self.STATE_CONNECTING

    def start(self):
        if not self.should_run:
            self.telephone.announce()
            self.should_run = True
            self.run()

    def stop(self):
        self.should_run = False

    def call(self, remote_identity):
        print(f"Calling {RNS.prettyhexrep(remote_identity.hash)}...")
        self.state = self.STATE_CONNECTING
        self.caller = remote_identity
        self.direction = "to"
        self.telephone.call(self.caller)

    def ringing(self, remote_identity):
        self.state = self.STATE_RINGING
        self.caller  = remote_identity
        self.direction = "from" if self.direction == None else "to"
        print(f"\n\nIncoming call from {RNS.prettyhexrep(self.caller.hash)}")
        print(f"Hit enter to answer, {Terminal.BOLD}r{Terminal.END} to reject")

    def call_ended(self, remote_identity):
        if self.is_in_call or self.is_ringing or self.call_is_connecting:
            if self.is_in_call:         print(f"Call with {RNS.prettyhexrep(self.caller.hash)} ended\n")
            if self.is_ringing:         print(f"Call {self.direction} {RNS.prettyhexrep(self.caller.hash)} was not answered\n")
            if self.call_is_connecting: print(f"Call to {RNS.prettyhexrep(self.caller.hash)} could not be connected\n")
            self.direction = None
            self.state = self.STATE_AVAILABLE
            self.became_available()

    def call_established(self, remote_identity):
        if self.call_is_connecting or self.is_ringing:
            self.state = self.STATE_IN_CALL
            print(f"Call established with {RNS.prettyhexrep(self.caller.hash)}")
            self.display_call_status()

    def display_call_status(self):
        def job():
            started = time.time()
            erase_str = ""
            while self.state == self.STATE_IN_CALL:
                elapsed      = round(time.time()-started)
                stat_string  = "{elapsed}. Hit enter to hang up."
                print(f"\r{erase_str}", end="")
                print(f"\r{stat_string}", end="")
                erase_string = " "*len(stat_string)
                sys.stdout.flush()
        threading.Thread(target=job, daemon=True).start()

    def became_available(self):
        if self.is_available and self.first_run:
            hs = ""
            if not hasattr(self, "first_prompt"): hs = " (or ? for help)"; self.first_prompt = True
            print(f"Enter identity hash and hit enter to call{hs}\n", end="")
        print("> ", end="")
        sys.stdout.flush()

    def main_menu(self):
        def m_help(argv):
            print("")
            print(f"{Terminal.UNDERLINE}Available commands{Terminal.END}")
            print(f"  {Terminal.BOLD}q{Terminal.END}uit  : Exit the program")
            print(f"  {Terminal.BOLD}h{Terminal.END}elp  : This help menu")
            print("")
        
        def m_quit(argv):
            exit(0)

        self.active_menu = {"help": m_help,
                            "h": m_help,
                            "?": m_help,
                            "exit": m_quit,
                            "quit": m_quit,
                            "q": m_quit}

    def run(self):
        print(f"\n{Terminal.BOLD}Reticulum Telephone Utility is ready{Terminal.END}")
        print(f"  Identity hash: {RNS.prettyhexrep(self.identity.hash)}\n")
        while self.should_run:
            if self.is_available:
                if self.last_input and len(self.last_input) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2:
                    if self.is_available:
                        try:
                            self.telephone.set_busy(True)
                            identity_hash = bytes.fromhex(self.last_input)
                            destination_hash = RNS.Destination.hash_from_name_and_identity("lxst.telephony", identity_hash)
                            if not RNS.Transport.has_path(destination_hash):
                                RNS.Transport.request_path(destination_hash)
                                def spincheck():
                                    return RNS.Transport.has_path(destination_hash)
                                self.__spin(spincheck, "Requesting path for call to "+RNS.prettyhexrep(identity_hash), self.path_time)
                                if not spincheck():
                                    print("Path request timed out")
                                    self.became_available()

                            self.telephone.set_busy(False)
                            if RNS.Transport.has_path(destination_hash):
                                identity = RNS.Identity.recall(destination_hash)
                                self.call(identity)

                        except Exception as e:
                            print(f"Invalid identity hash: {e}\n")
                            RNS.trace_exception(e)

                elif self.last_input and self.last_input.split(" ")[0] in self.active_menu:
                    self.active_menu[self.last_input.split(" ")[0]](self.last_input.split(" ")[1:])
                    self.became_available()

                else:
                    self.became_available()

            elif self.is_ringing:
                if self.last_input == "":
                    print(f"Answering call from {RNS.prettyhexrep(self.caller.hash)}")
                    if not self.telephone.answer(self.caller):
                        print(f"Could not answer call from {RNS.prettyhexrep(self.caller.hash)}")
                else:
                    print(f"Rejecting call from {RNS.prettyhexrep(self.caller.hash)}")
                    self.telephone.hangup()

            elif self.is_in_call or self.call_is_connecting:
                print(f"Hanging up call with {RNS.prettyhexrep(self.caller.hash)}")
                self.telephone.hangup()

            self.last_input = input()

    def __spin(self, until=None, msg=None, timeout=None):
        i = 0
        syms = "⢄⢂⢁⡁⡈⡐⡠"
        if timeout != None:
            timeout = time.time()+timeout

        print(msg+"  ", end=" ")
        while (timeout == None or time.time()<timeout) and not until():
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

        print("\r"+" "*len(msg)+"  \r", end="")

        if timeout != None and time.time() > timeout:
            return False
        else:
            return True

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

__default_rnphone_config__ = """# This is an example rnphone config file.
# You should probably edit it to suit your
# intended usage.
"""

class Terminal():
    UNDERLINE = "\033[4m"
    BOLD = "\033[1m"
    END = "\033[0m"

if __name__ == "__main__":
    main()