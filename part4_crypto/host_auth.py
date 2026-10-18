"""
host_auth.py - PC side of the Q-PUF authentication demo.
  * plays the PUF DEVICE (uses the Part-1 simulator + Part-3 fuzzy extractor + Part-4 hash)
  * talks to the VERIFIER (a real microcontroller over serial, or a pure-Python stand-in).

  python host_auth.py demo --sim                 # no hardware needed
  python host_auth.py demo --port COM5           # real board (Linux: /dev/ttyUSB0, /dev/ttyACM0)
  python host_auth.py selftest --port COM5       # check the board's hash against the Python golden model
"""
import argparse, json, os, subprocess, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("../part1_device", "../part3_fuzzy", "python"):
    sys.path.insert(0, os.path.join(HERE, sub))
from qpuf_model import *
from fuzzy_ref import enroll as fe_enroll, reproduce as fe_reproduce, to_bytes
from ascon_hash import ascon_hash, derive_key, make_tag

# ------------------------------------------------------------------ verifier back-ends
class PyBoard:
    """Pure-Python stand-in that speaks exactly the same line protocol as the firmware."""
    def __init__(self): self.keys, self.nonce = {}, {}
    def cmd(self, line):
        t = line.split()
        if t[0] == "PING": return "PONG"
        if t[0] == "HASH": return "DIGEST " + ascon_hash(bytes.fromhex(t[1] if len(t) > 1 else "")).hex()
        i = int(t[1])
        if t[0] == "ENROLL": self.keys[i] = bytes.fromhex(t[2]); self.nonce.pop(i, None); return f"ENROLLED {i}"
        if t[0] == "CHAL":   self.nonce[i] = os.urandom(16); return "NONCE " + self.nonce[i].hex()
        if t[0] == "RESP":
            if i not in self.nonce: return "FAIL 0"
            n = self.nonce.pop(i); ok = make_tag(self.keys[i], n) == bytes.fromhex(t[2])
            return ("OK " if ok else "FAIL ") + "0"

class SerialBoard:
    def __init__(self, port, baud=115200):
        import serial                                   # pip install pyserial
        self.s = serial.Serial(port, baud, timeout=2); time.sleep(2.0)   # boards reset on open
        self.s.reset_input_buffer()
    def cmd(self, line):
        self.s.write((line + "\n").encode()); return self.s.readline().decode().strip()

class ExeBoard:
    """Runs the real firmware logic compiled for the PC (see tools/arduino_shim) - for testing."""
    def __init__(self, exe):
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    def cmd(self, line):
        self.p.stdin.write(line + "\n"); self.p.stdin.flush(); return self.p.stdout.readline().strip()

# ------------------------------------------------------------------ protocol
def enroll(dev, challenge, board, slot, rng, rec_dir=None, qualify=20):
    """Enroll a device. 'Qualification': re-read the PUF `qualify` times and only accept a
    (challenge, helper-data) pair whose secret is reproduced every time; otherwise try the
    next challenge number. (~4 % of challenges are unlucky and get rejected here.)"""
    for attempt in range(10):
        C = int(challenge) + 1000 * attempt
        R = golden_response(dev, C)                           # clean enrollment response
        secret, W = fe_enroll(R, rng)                         # helper data W is PUBLIC
        if all(np.array_equal(fe_reproduce(read_response(dev, C, NOMINAL, rng, n_reads=N_READS_FIELD), W)[0], secret)
               for _ in range(qualify)):
            break
    key = derive_key(to_bytes(secret))
    assert board.cmd(f"ENROLL {slot} {key.hex()}").startswith("ENROLLED")
    rec = dict(device_id=dev.id, slot=slot, challenge=C, helper=bits_to_hex(W), attempts=attempt + 1)
    if rec_dir:
        os.makedirs(rec_dir, exist_ok=True)
        json.dump(rec, open(os.path.join(rec_dir, f"device{dev.id}.json"), "w"))
    return rec

def authenticate_bits(raw_bits, rec, board):
    """Run one authentication using the given raw response bits (genuine OR forged)."""
    W = hex_to_bits(rec["helper"])
    secret, err = fe_reproduce(raw_bits, W)
    key = derive_key(to_bytes(secret))
    nonce = bytes.fromhex(board.cmd(f"CHAL {rec['slot']}").split()[1])
    tag = make_tag(key, nonce)
    reply = board.cmd(f"RESP {rec['slot']} {tag.hex()}")
    return reply.startswith("OK"), err, reply, tag

def authenticate(dev, rec, board, env, rng):
    bits = read_response(dev, rec["challenge"], env, rng, n_reads=N_READS_FIELD)
    return authenticate_bits(bits, rec, board)

# ------------------------------------------------------------------ demo
def demo(board, trials=64, n_dev=8):
    """Each scenario is run on n_dev different devices (trials // n_dev attempts each)."""
    rng = np.random.default_rng(1)
    per = max(1, trials // n_dev)
    hot, aged = dict(temp_c=85.0, age_years=0.0), dict(temp_c=25.0, age_years=10.0)
    scenarios = {
        "genuine device, 25 C":  lambda d, rec: authenticate(d, rec, board, NOMINAL, rng),
        "genuine device, 85 C":  lambda d, rec: authenticate(d, rec, board, hot, rng),
        "genuine, 10 yr aged":   lambda d, rec: authenticate(d, rec, board, aged, rng),
        "CLONE (other device)":  lambda d, rec: authenticate(QPUFDevice(1000 + d.id), rec, board, NOMINAL, rng),
        "random 896-bit guess":  lambda d, rec: authenticate_bits(rng.integers(0, 2, RAW_LEN, dtype=np.uint8), rec, board),
    }
    acc = {k: [0, 0, 0] for k in list(scenarios) + ["replay of old tag"]}      # ok, corrected bits, count
    lat = []
    for dev_id in range(1, n_dev + 1):
        dev = QPUFDevice(dev_id)
        rec = enroll(dev, 4000 + dev_id, board, slot=0, rng=rng)
        for name, fn in scenarios.items():
            for _ in range(per):
                ok, err, reply, _ = fn(dev, rec)
                acc[name][0] += ok; acc[name][1] += err; acc[name][2] += 1
                if reply.startswith("OK") and reply.split()[1] != "0": lat.append(int(reply.split()[1]))
        # replay: capture one valid tag, then present it against a NEW nonce
        _, _, _, old_tag = authenticate(dev, rec, board, NOMINAL, rng)
        for _ in range(per):
            board.cmd(f"CHAL {rec['slot']}")
            ok = board.cmd(f"RESP {rec['slot']} {old_tag.hex()}").startswith("OK")
            acc["replay of old tag"][0] += ok; acc["replay of old tag"][2] += 1
    print(f"\n{'scenario':26s} {'accepted %':>10s} {'avg corrected bits':>20s}")
    for n, (ok, err, cnt) in acc.items(): print(f"{n:26s} {100.0*ok/cnt:10.1f} {err/cnt:20.1f}")
    if lat: print(f"\nboard tag-computation time: {np.mean(lat):.0f} us on average ({len(lat)} measurements)")

def selftest(board):
    for m in ("", "616263", bytes(range(32)).hex(), bytes(range(64)).hex()):
        got = board.cmd(f"HASH {m}").split()[1]; exp = ascon_hash(bytes.fromhex(m)).hex()
        print(f"len={len(m)//2:2d} bytes:", "MATCH" if got == exp else f"MISMATCH {got} != {exp}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["demo", "selftest"])
    ap.add_argument("--port"); ap.add_argument("--sim", action="store_true"); ap.add_argument("--exe")
    ap.add_argument("--trials", type=int, default=64)
    a = ap.parse_args()
    board = SerialBoard(a.port) if a.port else ExeBoard(a.exe) if a.exe else PyBoard()
    print("board says:", board.cmd("PING"))
    demo(board, a.trials) if a.action == "demo" else selftest(board)
