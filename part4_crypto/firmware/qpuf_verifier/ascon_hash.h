/* ascon_hash.h - header-only Ascon-Hash (Ascon v1.2, 256-bit digest).
 * Portable C: works on PC (gcc), Arduino (AVR/ESP32/STM32 cores) and any 32/64-bit MCU.
 * Matches python/ascon_hash.py and the official KAT vectors.                          */
#ifndef ASCON_HASH_H
#define ASCON_HASH_H
#include <stdint.h>
#include <stddef.h>

#define ASCON_HASH_IV 0x00400c0000000100ULL

static inline uint64_t ascon_ror(uint64_t x, int n) { return (x >> n) | (x << (64 - n)); }

static void ascon_p12(uint64_t s[5]) {
  uint8_t c = 0xf0;                              /* round constants f0,e1,d2,... (-0x0f each) */
  for (int i = 0; i < 12; i++, c -= 0x0f) {
    uint64_t x0 = s[0], x1 = s[1], x2 = s[2], x3 = s[3], x4 = s[4], t0, t1, t2, t3, t4;
    x2 ^= c;                                              /* add round constant        */
    x0 ^= x4; x4 ^= x3; x2 ^= x1;                         /* substitution layer        */
    t0 = ~x0 & x1; t1 = ~x1 & x2; t2 = ~x2 & x3; t3 = ~x3 & x4; t4 = ~x4 & x0;
    x0 ^= t1; x1 ^= t2; x2 ^= t3; x3 ^= t4; x4 ^= t0;
    x1 ^= x0; x0 ^= x4; x3 ^= x2; x2 = ~x2;
    s[0] = x0 ^ ascon_ror(x0, 19) ^ ascon_ror(x0, 28);    /* linear diffusion layer    */
    s[1] = x1 ^ ascon_ror(x1, 61) ^ ascon_ror(x1, 39);
    s[2] = x2 ^ ascon_ror(x2, 1)  ^ ascon_ror(x2, 6);
    s[3] = x3 ^ ascon_ror(x3, 10) ^ ascon_ror(x3, 17);
    s[4] = x4 ^ ascon_ror(x4, 7)  ^ ascon_ror(x4, 41);
  }
}

static uint64_t ascon_load_be(const uint8_t *p, size_t n) {   /* n <= 8 bytes, big-endian */
  uint64_t w = 0;
  for (size_t i = 0; i < n; i++) w |= (uint64_t)p[i] << (56 - 8 * i);
  return w;
}

static void ascon_hash(uint8_t *out, size_t outlen, const uint8_t *in, size_t inlen) {
  uint64_t s[5] = { ASCON_HASH_IV, 0, 0, 0, 0 };
  ascon_p12(s);                                          /* initialisation            */
  while (inlen >= 8) {                                   /* absorb full blocks        */
    s[0] ^= ascon_load_be(in, 8);
    ascon_p12(s);
    in += 8; inlen -= 8;
  }
  s[0] ^= ascon_load_be(in, inlen);                      /* last (partial) block      */
  s[0] ^= 0x8000000000000000ULL >> (8 * inlen);          /* padding bit '1'           */
  while (outlen > 0) {                                   /* squeeze                   */
    ascon_p12(s);
    for (int i = 0; i < 8 && outlen > 0; i++, outlen--) *out++ = (uint8_t)(s[0] >> (56 - 8 * i));
  }
}

/* --- helpers used by the Q-PUF protocol ------------------------------------------ */
static void qpuf_derive_key(uint8_t key[16], const uint8_t secret[16]) {
  uint8_t m[24] = { 'Q','P','U','F','-','K','E','Y' };
  for (int i = 0; i < 16; i++) m[8 + i] = secret[i];
  uint8_t d[32]; ascon_hash(d, 32, m, 24);
  for (int i = 0; i < 16; i++) key[i] = d[i];
}
static void qpuf_make_tag(uint8_t tag[16], const uint8_t key[16], const uint8_t nonce[16]) {
  uint8_t m[32];
  for (int i = 0; i < 16; i++) { m[i] = key[i]; m[16 + i] = nonce[i]; }
  uint8_t d[32]; ascon_hash(d, 32, m, 32);
  for (int i = 0; i < 16; i++) tag[i] = d[i];
}
#endif
