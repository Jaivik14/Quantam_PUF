"""
ascon_hash.py - golden reference for Ascon-Hash (Ascon v1.2, 256-bit digest).
Used to (1) derive keys, (2) build tags, (3) generate test vectors for SystemVerilog and C.
"""
M64 = (1 << 64) - 1
RC = [0xf0, 0xe1, 0xd2, 0xc3, 0xb4, 0xa5, 0x96, 0x87, 0x78, 0x69, 0x5a, 0x4b]  # 12-round constants

def ror(x, n):
    return ((x >> n) | (x << (64 - n))) & M64

def ascon_round(x, c):
    x0, x1, x2, x3, x4 = x
    x2 ^= c                                   # 1) add round constant
    x0 ^= x4; x4 ^= x3; x2 ^= x1              # 2) substitution layer (bit-sliced 5-bit S-box)
    t0 = (~x0) & x1; t1 = (~x1) & x2; t2 = (~x2) & x3; t3 = (~x3) & x4; t4 = (~x4) & x0
    x0 ^= t1; x1 ^= t2; x2 ^= t3; x3 ^= t4; x4 ^= t0
    x1 ^= x0; x0 ^= x4; x3 ^= x2; x2 = ~x2 & M64
    x0 ^= ror(x0, 19) ^ ror(x0, 28)           # 3) linear diffusion layer
    x1 ^= ror(x1, 61) ^ ror(x1, 39)
    x2 ^= ror(x2, 1)  ^ ror(x2, 6)
    x3 ^= ror(x3, 10) ^ ror(x3, 17)
    x4 ^= ror(x4, 7)  ^ ror(x4, 41)
    return [v & M64 for v in (x0, x1, x2, x3, x4)]

def permute(x, rounds=12):
    for c in RC[12 - rounds:]:
        x = ascon_round(x, c)
    return x

IV = 0x00400c0000000100

def ascon_hash(msg: bytes, outlen: int = 32) -> bytes:
    s = permute([IV, 0, 0, 0, 0])                       # initialise
    padded = msg + b"\x80"
    padded += b"\x00" * ((-len(padded)) % 8)            # pad to multiple of 8 bytes
    blocks = [int.from_bytes(padded[i:i + 8], "big") for i in range(0, len(padded), 8)]
    for b in blocks[:-1]:                               # absorb all but last block
        s[0] ^= b
        s = permute(s)
    s[0] ^= blocks[-1]                                  # last block: xor, no permute yet
    out = b""
    while len(out) < outlen:                            # squeeze
        s = permute(s)
        out += s[0].to_bytes(8, "big")
    return out[:outlen]

def derive_key(secret16: bytes) -> bytes:
    """128-bit key from the 128-bit fuzzy-extractor secret."""
    return ascon_hash(b"QPUF-KEY" + secret16)[:16]

def make_tag(key16: bytes, nonce16: bytes) -> bytes:
    """128-bit authentication tag = first 16 bytes of Ascon-Hash(key || nonce)."""
    return ascon_hash(key16 + nonce16)[:16]

if __name__ == "__main__":
    print(ascon_hash(b"").hex())
