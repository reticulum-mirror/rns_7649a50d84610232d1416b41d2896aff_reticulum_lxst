# Lightweight Extensible Signal Transport

LXST is a simple and flexible real-time streaming format and delivery protocol that allows a wide variety of implementations, while using as little bandwidth as possible. It is built on top of [Reticulum](https://reticulum.network) and offers zero-conf stream routing, end-to-end encryption and Forward Secrecy, and can be transported over any kind of medium that Reticulum supports.

- Provides a variety of ready-to-use primitives, for easily creating applications such as:
  - Telephony and live voice calls
  - Two-way radio systems
  - Trunked and routed real-time two-way radio systems
  - Media streaming
- Can handle real-time signal streams with end-to-end latencies below 10 milliseconds
- Supports encoding and decoding stream contents with a range of different codecs
  - Raw and lossless streams with arbitrary sample rates
    - Up to 32 channels
    - Up to 128-bit sample bitdepths
  - Efficient, high-quality voice and audio with OPUS
    - Many different built-in profiles, from ~4.5kbps to ~96kbps
    - Profiles are pre-tuned for different applications, such as:
      - Low-bandwidth voice
      - Medium quality voice
      - High quality, perceptually lossless voice
      - Media content such as podcasts
      - Perceptually lossless stereo music
  - Ultra low-bandwidth voice communications with Codec2
    - Provides intelligible voice between 700bps and 3200bps
- Has in-band signalling support for call, communications, media and stream management

## Transport Encryption

LXST uses encryption provided by [Reticulum](https://reticulum.network), and thus uses end-to-end encryption by default.

## Project Status & License

This software is in a very early alpha state, and will change rapidly with ongoing development. Consider no APIs stable. Consider everything explosive.

While under early development, the project is kept under a `CC BY-NC-ND 4.0` license. Final target license is GPLv3 or MIT.

## Installation

If you want to try out LXST, you can install it with pip:

```bash
pip install lxst
```
