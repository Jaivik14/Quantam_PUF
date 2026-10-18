/* usage: ./test_ascon <hex message>   -> prints digest hex (used by tests/run_kat_c.py) */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "ascon_hash.h"
int main(int argc, char **argv) {
  uint8_t msg[2048]; size_t n = 0;
  const char *h = argc > 1 ? argv[1] : "";
  for (; h[0] && h[1]; h += 2) { unsigned v; sscanf(h, "%2x", &v); msg[n++] = (uint8_t)v; }
  uint8_t d[32]; ascon_hash(d, 32, msg, n);
  for (int i = 0; i < 32; i++) printf("%02x", d[i]);
  printf("\n"); return 0;
}
