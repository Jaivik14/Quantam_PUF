"""Create test-vector files for the SystemVerilog fuzzy extractor testbench."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "part1_device"))
from qpuf_model import *
from fuzzy_ref import *

OUT = os.path.join(os.path.dirname(__file__), "tb")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)
H = lambda bits: bits_to_hex(bits)

def write_rep(name, triples):
    with open(os.path.join(OUT, name), "w") as f:
        for Rn, W, s in triples:
            _, err = reproduce(Rn, W)
            f.write(f"{H(Rn)} {H(W)} {H(s)} {err}\n")

# 1) iid bit-flip vectors at several raw BERs (for the failure-rate curve)
for ber in (0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15):
    rows = []
    for _ in range(1000):
        R = rng.integers(0, 2, RAW_LEN, dtype=np.uint8)
        s, W = enroll(R, rng)
        flips = (rng.random(RAW_LEN) < ber).astype(np.uint8)
        rows.append((R ^ flips, W, s))
    write_rep(f"rep_ber{int(ber*100):02d}.txt", rows)

# 2) realistic vectors from the Part-1 simulator (nominal and hot)
for tag, env in (("nominal", NOMINAL), ("hot85", dict(temp_c=85.0, age_years=0.0))):
    rows = []
    for i in range(200):
        dev = QPUFDevice(i)
        C = 5000 + i
        R = golden_response(dev, C)
        s, W = enroll(R, rng)
        Rn = read_response(dev, C, env, rng, n_reads=N_READS_FIELD)
        rows.append((Rn, W, s))
    write_rep(f"rep_sim_{tag}.txt", rows)

# 3) enrollment-mode vectors: R, s -> W
with open(os.path.join(OUT, "enroll_vectors.txt"), "w") as f:
    for _ in range(100):
        R = rng.integers(0, 2, RAW_LEN, dtype=np.uint8)
        s, W = enroll(R, rng)
        f.write(f"{H(R)} {H(s)} {H(W)}\n")
print("vectors written to", OUT)
