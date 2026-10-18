"""
run_attacks.py - runs every Part-5 experiment and writes results.json.   python run_attacks.py
Takes ~3-5 minutes. Each experiment prints as it finishes.
"""
import json, os, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "part3_fuzzy"))
from attacks import *
from fuzzy_ref import enroll, reproduce

rng = np.random.default_rng(5)
target = QPUFDevice(424242)
OUT = {}
def log(key, val):
    OUT[key] = val; print(key, "->", json.dumps(val), flush=True)
    json.dump(OUT, open(os.path.join(HERE, "results.json"), "w"), indent=2)

# ---------------- A. plain Q-PUF (XOR-1): accuracy vs number of leaked CRP bits -------------
te_sp, te_y = collect(target, 90000 + np.arange(25), 1, rng, golden=True)       # 22,400 test bits
A = {}
for ntr in (1, 5, 20, 72):                                                      # challenges = 896 bits each
    tr_sp, tr_y = collect(target, 100 + np.arange(ntr), 1, rng)
    res, _ = attack_xor1(tr_sp, tr_y, te_sp, te_y)
    A[str(ntr * 896)] = {k: round(v, 3) for k, v in res.items()}
log("A_xor1_accuracy_vs_training_bits", A)

# ---------------- B. XOR-k hardening vs the product-model attack ----------------------------
B = {}
for k in (2, 3):
    te_k, te_yk = collect(target, 90000 + np.arange(12), k, rng, golden=True)
    for ntr in (5, 20):
        tr_k, tr_yk = collect(target, 100 + np.arange(ntr), k, rng)
        res, _ = attack_xork(tr_k, tr_yk, te_k, te_yk)
        B[f"XOR-{k}, {ntr*896} bits"] = round(res["product-model"], 3)
log("B_xork_product_attack_accuracy", B)

# ---------------- C. full forgery with leaked RAW bits ----------------------------------------
def forge_rate(predict_bits, n_trials=100, base=70000):
    ok = 0
    for i in range(n_trials):
        C = base + i
        R = read_response(target, C, NOMINAL, rng, n_reads=31)
        s, W = enroll(R, rng)
        s_hat, _ = reproduce(predict_bits(C), W)
        ok += int(np.array_equal(s, s_hat))
    return round(ok / n_trials, 3)
genuine = forge_rate(lambda C: read_response(target, C, NOMINAL, rng, n_reads=N_READS_FIELD))
Cc = {"genuine device (reference)": genuine}
for ntr in (1, 2, 5, 20):
    tr_sp, tr_y = collect(target, 100 + np.arange(ntr), 1, rng)
    _, lr = attack_xor1(tr_sp, tr_y, te_sp, te_y)
    pred = lambda C, lr=lr: lr.predict(structured(*(a[:, 0] for a in expand_challenge(C, RAW_LEN, 1)))).astype(np.uint8)
    Cc[f"attacker with {ntr*896} leaked bits"] = forge_rate(pred)
log("C_forgery_success_rate_raw_bits_leaked", Cc)

# ---------------- D. attack using ONLY the public helper data -----------------------------------
def helper_pair_labels(challenges):
    X1, X2, Y = [], [], []
    for C in challenges:
        R = read_response(target, C, NOMINAL, rng, n_reads=31); _, W = enroll(R, rng)      # what an eavesdropper sees: W only
        qa, qb, th, t = (a[:, 0] for a in expand_challenge(C, RAW_LEN, 1))
        i = np.array([g * REP + j for g in range(KEY_BITS) for j in range(REP - 1)])          # adjacent bits in the same group
        S = structured(qa, qb, th, t)
        X1.append(S[i]); X2.append(S[i + 1]); Y.append(W[i] ^ W[i + 1])                       # = R[i] xor R[i+1]  (secret cancels!)
    return [np.vstack(X1), np.vstack(X2)], np.concatenate(Y)
Dres = {}
for m in (3, 10, 30):
    Xs, y = helper_pair_labels(5000 + np.arange(m))
    w = fit_product(Xs, y, restarts=3)
    ok = 0
    for i in range(100):
        C = 70000 + i
        R = read_response(target, C, NOMINAL, rng, n_reads=31); s, W = enroll(R, rng)
        u = structured(*(a[:, 0] for a in expand_challenge(C, RAW_LEN, 1))) @ w
        s_hat, _ = reproduce((u > 0).astype(np.uint8), W)
        ok += int(np.array_equal(s, s_hat) or np.array_equal(s, 1 - s_hat))                  # sign ambiguity: 2 online guesses
    Dres[f"{m} public helper-data sets ({len(y)} XOR labels)"] = round(ok / 100, 3)
log("D_forgery_from_helper_data_only", Dres)

# ---------------- E. does adding qubits help? -------------------------------------------------------
E = {}
for nq in (16, 32, 64, 128):
    dev = QPUFDevice(424242, n_q=nq)
    tr_sp, tr_y = collect(dev, 100 + np.arange(10), 1, rng)
    te_s, te_yy = collect(dev, 90000 + np.arange(12), 1, rng, golden=True)
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(C=100, max_iter=2000, fit_intercept=False).fit(structured(*(a[:, 0] for a in tr_sp), n_q=nq), tr_y)
    E[f"{nq} qubits"] = round(acc(lr.predict(structured(*(a[:, 0] for a in te_s), n_q=nq)), te_yy), 3)
log("E_accuracy_with_8960_leaked_bits_vs_qubits", E)
print("done")
