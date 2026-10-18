// Minimal Arduino shim so firmware/qpuf_verifier/qpuf_verifier.ino can run on a PC (stdin/stdout = Serial).
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <unistd.h>
#include <sys/select.h>
#define A0 0
struct SerialShim {
  unsigned char buf[4096]; int n = 0, pos = 0; bool eof = false;
  void begin(int) {}
  int available() {
    if (pos < n) return n - pos;
    if (eof) return 0;
    fd_set f; FD_ZERO(&f); FD_SET(0, &f); timeval tv{0, 100000};
    if (select(1, &f, 0, 0, &tv) > 0) {
      int r = (int)::read(0, buf, sizeof(buf));
      if (r <= 0) { eof = true; return 0; }
      n = r; pos = 0; return n;
    }
    return 0;
  }
  int read() { return pos < n ? buf[pos++] : -1; }
  void print(const char *s) { fputs(s, stdout); }
  void print(char c) { putchar(c); }
  void print(int v) { printf("%d", v); }
  void print(unsigned long v) { printf("%lu", v); }
  void println() { putchar('\n'); fflush(stdout); }
  void println(const char *s) { fputs(s, stdout); putchar('\n'); fflush(stdout); }
  void println(int v) { printf("%d\n", v); fflush(stdout); }
  void println(unsigned long v) { printf("%lu\n", v); fflush(stdout); }
};
static SerialShim Serial;
static inline unsigned long micros() {
  return (unsigned long)std::chrono::duration_cast<std::chrono::microseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
static inline long random(long m) { return rand() % m; }
static inline void randomSeed(unsigned long s) { srand((unsigned)s); }
static inline int analogRead(int) { return 0; }
