"""
attacks.py - Part 5: machine-learning modeling attacks on the Q-PUF.

Threat model: the attacker has seen N raw (challenge-spec -> response-bit) pairs of ONE target
device (for example through a debug port) and knows the public challenge-expansion algorithm.
Goal: predict the target's response bits for NEW challenges, i.e. build a software clone.
"""
import os, sys
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "part1_device"))
from qpuf_model import *

# ----------------------------------------------------------------------------------------
# 1. Collect CRPs the way an attacker would
# ----------------------------------------------------------------------------------------
def collect(dev, challenges, xor_k, rng, n_per=896, n_reads=9, golden=False):
    """Returns specs (qa,qb,th,t each shape (N,k)) and response bits y (N,)."""
    S = [[], [], [], []]; Y = []
    for C in challenges:
        sp = expand_challenge(int(C), n_per, xor_k, dev.n_q)
        for lst, a in zip(S, sp): lst.append(a)
        if golden:
            Y.append(read_response(dev, int(C), NOMINAL, rng, n=n_per, xor_k=xor_k, n_reads=31))
        else:
            Y.append(read_response(dev, int(C), NOMINAL, rng, n=n_per, xor_k=xor_k, n_reads=n_reads))
    return tuple(np.concatenate(s) for s in S), np.concatenate(Y)

# ----------------------------------------------------------------------------------------
# 2. Feature maps
# ----------------------------------------------------------------------------------------
def phi(th, t):
    """Physics-inspired basis: P(1) of a qubit is ~ (1-cos(th+eps))/2 * exp(-t/T1)."""
    w = t / 150.0; c, s = np.cos(th), np.sin(th)
    return np.stack([np.ones_like(th), c, s, w, w * c, w * s, w**2, w**2 * c, w**2 * s], -1)

def structured(qa, qb, th, t, n_q=N_Q):
    """Antisymmetric one-hot (x) phi feature:  (e_qa - e_qb) (x) phi(th, t).
    A LINEAR model on this feature can express  P1(qa) - P1(qb)  for every qubit pair."""
    n = len(qa); f = phi(th, t); X = np.zeros((n, n_q, f.shape[1]))
    idx = np.arange(n); X[idx, qa] += f; X[idx, qb] -= f
    return X.reshape(n, -1)

def raw_numeric(qa, qb, th, t):
    return np.stack([qa, qb, th, t], 1).astype(float)

def onehot_mix(qa, qb, th, t):
    n = len(qa); oh = np.zeros((n, 2 * N_Q)); idx = np.arange(n)
    oh[idx, qa] = 1; oh[idx, N_Q + qb] = 1
    return np.hstack([oh, np.cos(th)[:, None], np.sin(th)[:, None], (t / 150.0)[:, None]])

# ----------------------------------------------------------------------------------------
# 3. Attack models for XOR-1 (plain comparison)
# ----------------------------------------------------------------------------------------
def acc(pred, y): return float(np.mean(pred == y))

def attack_xor1(spec_tr, y_tr, spec_te, y_te):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neural_network import MLPClassifier
    sp = lambda s: tuple(a[:, 0] for a in s)
    tr, te = sp(spec_tr), sp(spec_te)
    out = {}
    lr = LogisticRegression(C=100, max_iter=2000, fit_intercept=False).fit(structured(*tr), y_tr)
    out["structured-LR"] = acc(lr.predict(structured(*te)), y_te)
    rf = RandomForestClassifier(100, n_jobs=-1, random_state=0).fit(raw_numeric(*tr), y_tr)
    out["random-forest"] = acc(rf.predict(raw_numeric(*te)), y_te)
    mlp = MLPClassifier((64, 32), max_iter=60, random_state=0).fit(onehot_mix(*tr), y_tr)
    out["MLP"] = acc(mlp.predict(onehot_mix(*te)), y_te)
    return out, lr

# ----------------------------------------------------------------------------------------
# 4. Product-of-tanh attack for XOR-k  (the "XOR-arbiter-PUF" style attack)
#    bit_k = XOR of k comparisons that all share ONE hidden weight vector w
#    model: z = (-1)^(k+1) * prod_i tanh(X_i . w)        label y = +1 if bit=1 else -1
# ----------------------------------------------------------------------------------------
def fit_product(Xs, y01, restarts=4, gamma=4.0, seed=0):
    k = len(Xs); y = 2.0 * y01 - 1.0; sign = (-1.0) ** (k + 1); N, dim = Xs[0].shape
    def loss_grad(w):
        u = [X @ w for X in Xs]; t = [np.tanh(a) for a in u]
        z = sign * np.prod(t, axis=0)
        m = gamma * y * z
        L = np.mean(np.logaddexp(0, -m))
        dLdz = -gamma * y / (1.0 + np.exp(m))
        g = np.zeros(dim)
        for i in range(k):
            others = np.prod([t[j] for j in range(k) if j != i], axis=0) if k > 1 else 1.0
            dz_du = sign * (1 - t[i] ** 2) * others
            g += Xs[i].T @ (dLdz * dz_du)
        return L, g / N
    rng = np.random.default_rng(seed); best = None
    for _ in range(restarts):
        w0 = rng.normal(0, 0.3, dim)
        r = minimize(loss_grad, w0, jac=True, method="L-BFGS-B", options=dict(maxiter=250))
        if best is None or r.fun < best.fun: best = r
    return best.x

def predict_product(Xs, w):
    k = len(Xs); z = ((-1.0) ** (k + 1)) * np.prod([np.tanh(X @ w) for X in Xs], axis=0)
    return (z > 0).astype(np.uint8)

def attack_xork(spec_tr, y_tr, spec_te, y_te):
    k = spec_tr[0].shape[1]
    Xtr = [structured(*(a[:, i] for a in spec_tr)) for i in range(k)]
    Xte = [structured(*(a[:, i] for a in spec_te)) for i in range(k)]
    w = fit_product(Xtr, y_tr)
    return {"product-model": acc(predict_product(Xte, w), y_te)}, w
