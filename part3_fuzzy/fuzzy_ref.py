"""
fuzzy_ref.py - golden software model of the code-offset fuzzy extractor (repetition code).
    Enrollment : pick random secret s;   W = R xor Rep(s)            (W is public helper data)
    Reproduce  : s' = Majority( R' xor W )  per group of REP bits    (R' = noisy re-read)
Bit order everywhere: array index 0 = most-significant bit of the hex string.
"""
import os, sys
import numpy as np
from math import comb
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "part1_device"))
from qpuf_model import KEY_BITS, REP, RAW_LEN

def rep_encode(s_bits):
    return np.repeat(s_bits, REP).astype(np.uint8)

def enroll(R, rng=None):
    """R: golden response (RAW_LEN bits). Returns (secret_bits, helper_W)."""
    rng = rng if rng is not None else np.random.default_rng()
    s = rng.integers(0, 2, KEY_BITS, dtype=np.uint8)
    return s, (R ^ rep_encode(s)).astype(np.uint8)

def reproduce(R_noisy, W):
    """Returns (secret_bits, err_est). err_est = number of bits the decoder had to flip."""
    noisy = (R_noisy ^ W).reshape(KEY_BITS, REP)
    ones = noisy.sum(axis=1)
    s = (ones * 2 > REP).astype(np.uint8)
    err = np.minimum(ones, REP - ones).sum()
    return s, int(err)

def p_block_fail(p, rep=REP):
    t = rep // 2
    return sum(comb(rep, k) * p**k * (1 - p)**(rep - k) for k in range(t + 1, rep + 1))

def p_key_fail(p, rep=REP, key_bits=KEY_BITS):
    return 1.0 - (1.0 - p_block_fail(p, rep)) ** key_bits

def to_bytes(bits):
    return np.packbits(bits).tobytes()

if __name__ == "__main__":
    for p in (0.02, 0.04, 0.06, 0.08, 0.10, 0.15):
        print(f"raw BER {p:.2f}: P(key fails) = {p_key_fail(p):.4%}")
