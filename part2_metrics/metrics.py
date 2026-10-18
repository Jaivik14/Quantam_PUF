"""
metrics.py - Part 2: PUF quality metrics + stress analysis on the Part-1 dataset.
Run:  python metrics.py          (needs ../data/qpuf_dataset.npz)
"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "part1_device"))
sys.path.insert(0, os.path.join(HERE, "..", "part3_fuzzy"))
from qpuf_model import KEY_BITS, REP, RAW_LEN
from fuzzy_ref import enroll, reproduce, p_key_fail
from nist_tests import TESTS

d = np.load(os.path.join(HERE, "..", "data", "qpuf_dataset.npz"))
G, NOM, TR, AR = d["golden"], d["nominal"], d["temp_reads"], d["age_reads"]
TEMPS, AGES = list(d["temps"]), list(d["ages"])
D, C = G.shape[:2]
os.makedirs(os.path.join(HERE, "plots"), exist_ok=True)
R = {}                                                     # results dictionary

# ---- 1. Uniformity: fraction of ones in each response (ideal 50 %) --------------------
uni = G.mean(axis=2)
R["uniformity_mean_%"] = round(100 * uni.mean(), 2)
R["uniformity_std_%"]  = round(100 * uni.std(), 2)

# ---- 2. Bit-aliasing: fraction of devices that output 1 at the same bit position -------
alias = G.mean(axis=0)                                      # (C, RAW_LEN)
R["bit_aliasing_mean_%"] = round(100 * alias.mean(), 2)
R["bit_aliasing_outside_40_60_%"] = round(100 * np.mean((alias < 0.4) | (alias > 0.6)), 2)

# ---- 3. Uniqueness: inter-device Hamming distance (ideal 50 %) ------------------------
inter = []
for c in range(C):
    x = G[:, c, :].astype(np.int16)
    for i in range(D):
        inter.extend(np.mean(x[i] != x[i + 1:], axis=1))
inter = np.array(inter)
p, s = inter.mean(), inter.std()
R["uniqueness_mean_%"] = round(100 * p, 2)
R["uniqueness_std_%"]  = round(100 * s, 2)
R["degrees_of_freedom_(entropy_estimate_bits)"] = round(p * (1 - p) / s ** 2, 1)   # Daugman

# ---- 4. Reliability: intra-device Hamming distance (BER) -------------------------------
def ber(reads):                                           # reads (D,C,S,RAW) vs golden (D,C,RAW)
    return np.mean(reads != G[..., None, :], axis=-1)
intra_nom = ber(NOM)                                       # (D, C, S)
R["BER_nominal_%"] = round(100 * intra_nom.mean(), 2)
R["BER_vs_temperature_%"] = {int(T): round(100 * np.mean(TR[i] != G[..., None, :]), 2) for i, T in enumerate(TEMPS)}
R["BER_vs_temperature_%"][25] = R["BER_nominal_%"]
R["BER_vs_age_years_%"]   = {int(A): round(100 * np.mean(AR[i] != G[..., None, :]), 2) for i, A in enumerate(AGES)}
R["BER_vs_age_years_%"][0] = R["BER_nominal_%"]

# ---- 5. End-to-end key failure rate through the fuzzy extractor ------------------------
rng = np.random.default_rng(3)
def key_fail(reads):
    bad = tot = 0
    for dd in range(D):
        for cc in range(C):
            sec, W = enroll(G[dd, cc], rng)
            for r in reads[dd, cc]:
                s2, _ = reproduce(r, W); bad += int(np.any(s2 != sec)); tot += 1
    return 100.0 * bad / tot
R["key_failure_rate_%"] = {"nominal_25C": round(key_fail(NOM), 2)}
for i, T in enumerate(TEMPS):  R["key_failure_rate_%"][f"{T}C"] = round(key_fail(TR[i]), 2)
for i, A in enumerate(AGES):   R["key_failure_rate_%"][f"{A}yr"] = round(key_fail(AR[i]), 2)
R["theory_key_failure_at_nominal_BER_%"] = round(100 * p_key_fail(R["BER_nominal_%"] / 100), 2)

# ---- 6. NIST tests: one sequence per device (all challenges concatenated) --------------
nist = {}
for name, fn in TESTS.items():
    pv = np.array([fn(G[i].reshape(-1)) for i in range(D)])
    nist[name] = round(100 * np.mean(pv >= 0.01), 1)       # pass proportion at alpha = 0.01
R["NIST_pass_proportion_%"] = nist

# ---- 7. Plots ---------------------------------------------------------------------------
intra_all = intra_nom.reshape(-1)
plt.figure(figsize=(6, 3.5))
plt.hist(100 * inter, bins=60, alpha=.7, density=True, label="inter-device (uniqueness)")
plt.hist(100 * intra_all, bins=40, alpha=.7, density=True, label="intra-device (noise)")
plt.xlabel("Hamming distance (%)"); plt.ylabel("density"); plt.legend(); plt.tight_layout()
plt.savefig(os.path.join(HERE, "plots", "hd_histograms.png"), dpi=150); plt.close()

Ts = sorted(R["BER_vs_temperature_%"]); As = sorted(R["BER_vs_age_years_%"])
fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
ax[0].plot(Ts, [R["BER_vs_temperature_%"][t] for t in Ts], "o-"); ax[0].set_xlabel("temperature (C)"); ax[0].set_ylabel("raw BER (%)")
ax[1].plot(As, [R["BER_vs_age_years_%"][a] for a in As], "s-");   ax[1].set_xlabel("aging (years)");    ax[1].set_ylabel("raw BER (%)")
for a in ax: a.grid(alpha=.3)
plt.tight_layout(); plt.savefig(os.path.join(HERE, "plots", "ber_stress.png"), dpi=150); plt.close()

plt.figure(figsize=(5, 3.3)); plt.hist(100 * alias.reshape(-1), bins=40)
plt.xlabel("bit-aliasing (% of devices with a '1')"); plt.ylabel("bit positions"); plt.tight_layout()
plt.savefig(os.path.join(HERE, "plots", "bit_aliasing.png"), dpi=150); plt.close()

json.dump(R, open(os.path.join(HERE, "results.json"), "w"), indent=2)
print(json.dumps(R, indent=2))
