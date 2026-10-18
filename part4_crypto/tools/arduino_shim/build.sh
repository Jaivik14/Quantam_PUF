#!/bin/sh
# Builds the firmware logic as a PC program:  ./build.sh  ->  ./qpuf_board_pc
cd "$(dirname "$0")" && g++ -O2 -x c++ main.cpp -o qpuf_board_pc
