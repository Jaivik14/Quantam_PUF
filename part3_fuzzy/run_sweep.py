"""Compile the RTL, run the testbench on every vector file, compare with theory."""
import glob, os, re, subprocess, sys
from fuzzy_ref import p_key_fail
here = os.path.dirname(os.path.abspath(__file__))
tb = os.path.join(here, "tb"); rtl = os.path.join(here, "rtl")
subprocess.run(["iverilog", "-g2012", "-o", "/tmp/tb_fz", f"{rtl}/fuzzy_extractor.sv",
                f"{rtl}/fuzzy_extractor_top.sv", f"{tb}/tb_fuzzy.sv"], check=True)
print(f"{'vector file':22s} {'RTL key-fail':>12s} {'theory':>8s}")
for f in sorted(glob.glob(f"{tb}/rep_*.txt")):
    out = subprocess.run(["vvp", "/tmp/tb_fz", f"+REPFILE={f}", f"+ENRFILE={tb}/enroll_vectors.txt"],
                         capture_output=True, text=True, cwd=tb).stdout
    m = re.search(r"key failures = (\d+) \(([\d.]+)%\)", out)
    name = os.path.basename(f)
    ber = re.search(r"ber(\d+)", name)
    theory = f"{p_key_fail(int(ber.group(1))/100):8.2%}" if ber else "   n/a"
    print(f"{name:22s} {m.group(2)+'%':>12s} {theory}")
