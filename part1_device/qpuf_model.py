"""
qpuf_model.py  -  Part 1: quantum-noise-inspired PUF device simulator.

A "device" is a small register of N_Q simulated qubits. Every device gets its own
random-but-fixed physical parameters (the "fabrication variation"):
    eps  : systematic over-rotation of the RY gate        [rad]
    T1   : energy-relaxation time                          [us]
    p01  : P(read 1 | qubit really in |0>)                 [-]
    p10  : P(read 0 | qubit really in |1>)                 [-]
A challenge selects (qubit pair, rotation angle, wait time) for each response bit.
The response bit is "which qubit of the pair shows the larger P(1)" - the same trick a
ring-oscillator PUF uses (compare two nominally identical elements).
"""
import numpy as np

N_Q      = 32        # qubits per device
REP      = 7         # repetition-code length used by the fuzzy extractor (Part 3)
KEY_BITS = 128       # secret length
RAW_LEN  = KEY_BITS * REP   # 896 raw response bits per challenge
SHOTS    = 2048      # measurement repetitions per circuit
N_READS_FIELD = 9    # temporal majority voting: reads per field measurement
MASTER_SEED = 2026   # makes every run reproducible

NOMINAL = dict(temp_c=25.0, age_years=0.0)

class QPUFDevice:
    def __init__(self, device_id: int, master_seed: int = MASTER_SEED, n_q: int = N_Q):
        rng = np.random.default_rng([master_seed, device_id])
        self.id  = device_id
        self.n_q = n_q
        self.eps = rng.normal(0.0, 0.08, n_q)                       # rad
        self.T1  = np.clip(rng.normal(100.0, 25.0, n_q), 40, 200)   # us
        self.p01 = np.clip(rng.normal(0.020, 0.006, n_q), 0.002, None)
        self.p10 = np.clip(rng.normal(0.040, 0.012, n_q), 0.005, None)
        # per-qubit sensitivities to the environment (also fixed per device)
        self.tc_dir  = rng.normal(0.0, 1.0, n_q)    # temperature drift direction
        self.age_dir = rng.normal(0.0, 1.0, n_q)    # aging drift direction

    def params_at(self, env):
        """Return (eps, T1, p01, p10) after applying temperature / aging."""
        dT, age = env["temp_c"] - 25.0, env["age_years"]
        eps = self.eps + 0.0006 * dT * self.tc_dir + 0.004 * age * self.age_dir
        T1  = self.T1 * (1.0 - 0.002 * dT)
        p10 = self.p10 * (1.0 + 0.004 * dT)
        return eps, T1, self.p01, p10


def expand_challenge(challenge: int, n: int = RAW_LEN, xor_k: int = 1, n_q: int = N_Q):
    """Public, deterministic expansion of a challenge number into n x xor_k
    measurement specs: qubit a, qubit b, rotation angle theta, wait time t."""
    rng = np.random.default_rng(challenge)
    qa = rng.integers(0, n_q, size=(n, xor_k))
    qb = (qa + rng.integers(1, n_q, size=(n, xor_k))) % n_q      # qb != qa
    th = rng.uniform(0.6, 2.5, size=(n, xor_k))                  # rad
    t  = rng.uniform(0.0, 150.0, size=(n, xor_k))                # us
    return qa, qb, th, t


def _p_obs(params, q, theta, t, jitter):
    eps, T1, p01, p10 = params
    ang = theta + eps[q] + jitter
    p1  = np.sin(ang / 2.0) ** 2 * np.exp(-t / T1[q])      # RY + T1 decay
    return p1 * (1.0 - p10[q]) + (1.0 - p1) * p01[q]        # readout error


def read_response(dev, challenge, env=NOMINAL, rng=None, n=RAW_LEN,
                  xor_k=1, shots=SHOTS, n_reads=1):
    """Measure the PUF. Returns a uint8 array of n bits (majority over n_reads)."""
    rng = rng if rng is not None else np.random.default_rng()
    qa, qb, th, t = expand_challenge(challenge, n, xor_k, dev.n_q)
    params = dev.params_at(env)
    reads = np.empty((n_reads, n), dtype=np.uint8)
    for r in range(n_reads):
        ja = rng.normal(0, 0.01, th.shape)                       # gate jitter
        jb = rng.normal(0, 0.01, th.shape)
        fa = rng.binomial(shots, _p_obs(params, qa, th, t, ja)) / shots
        fb = rng.binomial(shots, _p_obs(params, qb, th, t, jb)) / shots
        tie = rng.random(fa.shape) < 0.5
        bit = np.where(fa == fb, tie, fa > fb).astype(np.uint8)
        reads[r] = np.bitwise_xor.reduce(bit, axis=1)            # XOR-k
    if n_reads == 1:
        return reads[0]
    return (reads.sum(axis=0) * 2 > n_reads).astype(np.uint8)    # majority


def golden_response(dev, challenge, **kw):
    """'Enrollment quality' response: majority of 31 reads at nominal conditions."""
    return read_response(dev, challenge, NOMINAL, n_reads=31, **kw)


def bits_to_hex(bits):
    return np.packbits(bits).tobytes().hex()

def hex_to_bits(h, n=RAW_LEN):
    return np.unpackbits(np.frombuffer(bytes.fromhex(h), dtype=np.uint8))[:n]
