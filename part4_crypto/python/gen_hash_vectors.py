"""Generate test vectors for the SystemVerilog hash core and the auth unit."""
import os, random, sys
sys.path.insert(0, os.path.dirname(__file__))
from ascon_hash import ascon_hash, derive_key, make_tag
random.seed(7)
os.makedirs("../tb", exist_ok=True)
with open("../tb/hash_vectors.txt", "w") as f:        # format: <len_dec> <msg 64 hex> <digest 64 hex>
    for n in list(range(0, 33)) + [random.randint(0, 32) for _ in range(67)]:
        m = bytes(random.getrandbits(8) for _ in range(n))
        f.write(f"{n} {(m + bytes(32 - n)).hex()} {ascon_hash(m).hex()}\n")
with open("../tb/auth_vectors.txt", "w") as f:        # format: <secret 32 hex> <nonce 32 hex> <key 32 hex> <tag 32 hex>
    for _ in range(50):
        s, nn = os.urandom(16), os.urandom(16)
        k = derive_key(s)
        f.write(f"{s.hex()} {nn.hex()} {k.hex()} {make_tag(k, nn).hex()}\n")
print("vectors written")
