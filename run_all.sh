#!/bin/sh
# Full regression: every part, in order.  Needs: python3 (numpy scipy scikit-learn matplotlib), iverilog, gcc/g++
set -e
cd "$(dirname "$0")"
echo "== Part 1: dataset";  (cd part1_device && python3 gen_dataset.py)
echo "== Part 2: metrics";  (cd part2_metrics && python3 metrics.py)
echo "== Part 3: fuzzy extractor RTL"; (cd part3_fuzzy && python3 gen_vectors.py && python3 run_sweep.py)
echo "== Part 4: crypto";
(cd part4_crypto/python && python3 gen_hash_vectors.py)
(cd part4_crypto/tb && iverilog -g2012 -o /tmp/tb_hash ../rtl/ascon_hash_core.sv tb_ascon_hash_core.sv && vvp /tmp/tb_hash | tail -2)
(cd part4_crypto/tb && iverilog -g2012 -o /tmp/tb_auth ../rtl/ascon_hash_core.sv ../rtl/qpuf_auth_unit.sv tb_qpuf_auth_unit.sv && vvp /tmp/tb_auth | tail -2)
(cd part4_crypto && tools/arduino_shim/build.sh && python3 host_auth.py selftest --exe tools/arduino_shim/qpuf_board_pc && python3 host_auth.py demo --exe tools/arduino_shim/qpuf_board_pc)
echo "== Part 5: ML attacks (3-10 min)"; (cd part5_ml && python3 run_attacks.py)
