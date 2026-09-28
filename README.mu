>Lightweight Extensible Signal Transport

LXST is a simple and flexible real-time streaming format and delivery protocol that allows a wide variety of implementations, while using as little bandwidth as possible. It is built on top of `_`!`[Reticulum`https://reticulum.network]`!`_ and offers zero-conf stream routing, end-to-end encryption and Forward Secrecy, and can be transported over any kind of medium that Reticulum supports.

 • Cross-platform, works on Linux, Android, Windows and Mac
 • Provides a variety of ready-to-use primitives, for easily creating applications such as:
   • Telephony and live voice calls
   • Two-way radio systems
     • Direct peer-to-peer radio communications
     • Trunked and routed real-time radio systems
   • Media streaming
   • Broadcast radio
   • Public address systems
 • Can handle real-time signal streams with end-to-end latencies below 10 milliseconds
 • Supports encoding and decoding stream contents with a range of different codecs
   • Raw and lossless streams with arbitrary sample rates
     • Up to 32 channels
     • Up to 128-bit sample precision
   • Efficient, high-quality voice and audio with OPUS
     • Many different built-in profiles, from ~4.5kbps to ~96kbps
     • Profiles are pre-tuned for different applications, such as:
       • Low-bandwidth voice
       • Medium quality voice
       • High quality, perceptually lossless voice
       • Media content such as podcasts
       • Perceptually lossless stereo music
   • Ultra low-bandwidth voice communications with Codec2
     • Provides intelligible voice between 700bps and 3200bps
 • Can dynamically switch codecs mid-stream without stream re-initialization or frame loss
 • Has in-band signalling support for call signalling, communications, metadata embedding, media and stream management
 • Uses a fully staged signal pipelining, allowing arbitrary stream routing
 • Provides built-in signal mixing support for any number of channels

User-facing clients built on LXST include:

 • `_`!`[Sideband`https://unsigned.io/sideband]`!`_
 • `_`!`[MeshChatX`https://meshchatx.com/]`!`_
 • `_`!`[Partyline`https://github.com/RFnexus/partyline]`!`_
 • `_`!`[Columba`https://github.com/torlando-tech/columba]`!`_
 • `_`!`[rnphone`https://reticulum.network/manual/software.html]`!`_
 • `_`!`[LXST Phone`https://github.com/kc1awv/lxst_phone]`!`_

>>Transport Encryption

LXST uses encryption provided by `_`!`[Reticulum`https://reticulum.network]`!`_, and thus provides end-to-end encryption, guaranteed data integrity and authenticity, as well as forward secrecy by default.

>>Project Status & License

This software and its interfaces will change rapidly with ongoing development. Consider no APIs stable. Consider everything explosive. Not all features are implemented. Nothing is documented. For a fully functional LXST program, take a look at `_`!`[Sideband`https://github.com/markqvist/Sideband]`!`_ or the included `BT383838`Fdddrnphone`f`b program, which provides telephony service over Reticulum. Everything else will currently be a voyage of your own making.

The LXST project is available under a `BT383838`FdddCC BY-NC-ND 4.0`f`b license. You can deploy LXST freely for non-commercial, personal and humanitarian purposes. For commercial (including institutionalised educational) licensing, contact me.

>>Installation

If you want to try out LXST, you can install it with pip:

`BT282828`Fddd
pip install lxst
`f`b

On Raspberry Pi (assuming Trixie / Debian 13), install various dependencies with:

`BT282828`Fddd
`FT8b949e# Audio codecs`f
sudo apt install python3-pyaudio codec2

`FT8b949e# For hardware control over I2C:`f
pip install smbus2 --break-system-packages `FT8b949e# Install smbus module if not already installed`f
sudo raspi-config `FT8b949e# Enable the I2C bus under "Interface Options"`f
sudo apt install python3-rpi.gpio `FT8b949e# Install gpio module system-wide`f
`f`b