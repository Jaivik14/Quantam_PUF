"""Three NIST SP 800-22 tests written from scratch (monobit, runs, block-frequency)."""
import numpy as np
from math import erfc, sqrt
from scipy.special import gammaincc

def monobit(bits):
    n = len(bits); s = np.abs(np.sum(2 * bits.astype(int) - 1))
    return erfc(s / sqrt(n) / sqrt(2))

def runs(bits):
    n = len(bits); pi = bits.mean()
    if abs(pi - 0.5) >= 2 / sqrt(n):
        return 0.0
    v = 1 + np.sum(bits[1:] != bits[:-1])
    return erfc(abs(v - 2 * n * pi * (1 - pi)) / (2 * sqrt(2 * n) * pi * (1 - pi)))

def block_frequency(bits, M=128):
    N = len(bits) // M
    pis = bits[:N * M].reshape(N, M).mean(axis=1)
    chi2 = 4 * M * np.sum((pis - 0.5) ** 2)
    return gammaincc(N / 2, chi2 / 2)

TESTS = {"monobit": monobit, "runs": runs, "block_freq": block_frequency}
