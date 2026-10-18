"""Generate the multi-device dataset used by Parts 2, 3 and 5.   Run:  python gen_dataset.py"""
import os, time
import numpy as np
from qpuf_model import *

N_DEV   = 100
CHALLENGES = 1000 + np.arange(10)                 # 10 public challenge numbers
TEMPS   = [-20, 0, 55, 85]                         # deg C (25 = nominal)
AGES    = [2, 5, 10]                               # years
S_NOM, S_ENV = 5, 3                                # re-reads per (device, challenge, condition)

rng = np.random.default_rng(99)
t0 = time.time()
devs = [QPUFDevice(i) for i in range(N_DEV)]
shape = (N_DEV, len(CHALLENGES))
golden = np.zeros(shape + (RAW_LEN,), np.uint8)
nominal = np.zeros(shape + (S_NOM, RAW_LEN), np.uint8)
temp_reads = np.zeros((len(TEMPS),) + shape + (S_ENV, RAW_LEN), np.uint8)
age_reads  = np.zeros((len(AGES),)  + shape + (S_ENV, RAW_LEN), np.uint8)

for d, dev in enumerate(devs):
    for c, C in enumerate(CHALLENGES):
        golden[d, c] = golden_response(dev, int(C))
        for s in range(S_NOM):
            nominal[d, c, s] = read_response(dev, int(C), NOMINAL, rng, n_reads=N_READS_FIELD)
        for ti, T in enumerate(TEMPS):
            for s in range(S_ENV):
                temp_reads[ti, d, c, s] = read_response(dev, int(C), dict(temp_c=T, age_years=0.0), rng, n_reads=N_READS_FIELD)
        for ai, A in enumerate(AGES):
            for s in range(S_ENV):
                age_reads[ai, d, c, s] = read_response(dev, int(C), dict(temp_c=25.0, age_years=A), rng, n_reads=N_READS_FIELD)
    if d % 10 == 9:
        print(f"device {d+1}/{N_DEV}  ({time.time()-t0:.0f}s)")

os.makedirs("../data", exist_ok=True)
np.savez_compressed("../data/qpuf_dataset.npz", golden=golden, nominal=nominal,
                    temp_reads=temp_reads, age_reads=age_reads, challenges=CHALLENGES,
                    temps=TEMPS, ages=AGES)
print("saved ../data/qpuf_dataset.npz")
