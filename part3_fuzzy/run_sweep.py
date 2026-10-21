"""Compile the RTL, run the testbench on every vector file, compare with theory.
Works on Windows, Linux and macOS (needs iverilog and vvp on the PATH)."""
import glob, os, re, subprocess, sys
from pathlib import Path
from fuzzy_ref import p_key_fail

here = Path(__file__).resolve().parent
tb, rtl = here / "tb", here / "rtl"
out_vvp = tb / "tb_fz.vvp"                      # compiled file lives next to the testbench (no /tmp needed)

cmd = ["iverilog", "-g2012", "-o", str(out_vvp),
       str(rtl / "fuzzy_extractor.sv"), str(rtl / "fuzzy_extractor_top.sv"), str(tb / "tb_fuzzy.sv")]
try:
    subprocess.run(cmd, check=True)
except FileNotFoundError:
    sys.exit("iverilog not found. Install Icarus Verilog and tick 'Add to PATH' (then reopen the terminal).")

enr = (tb / "enroll_vectors.txt").as_posix()
print(f"{'vector file':22s} {'RTL key-fail':>12s} {'theory':>8s}")
for f in sorted(glob.glob(str(tb / "rep_*.txt"))):
    out = subprocess.run(["vvp", str(out_vvp), f"+REPFILE={Path(f).as_posix()}", f"+ENRFILE={enr}"],
                         capture_output=True, text=True, cwd=str(tb)).stdout
    m = re.search(r"key failures = (\d+) \(([\d.]+)%\)", out)
    name = os.path.basename(f)
    ber = re.search(r"ber(\d+)", name)
    theory = f"{p_key_fail(int(ber.group(1))/100):8.2%}" if ber else "   n/a"
    print(f"{name:22s} {(m.group(2) + '%') if m else 'ERROR':>12s} {theory}")