from .codec import Codec

class Raw(Codec):
    def __init__(self):
        pass

    def encode(self, samples):
        return samples

    def decode(self, samples):
        return samples