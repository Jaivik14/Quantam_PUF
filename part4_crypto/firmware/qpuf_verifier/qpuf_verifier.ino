/*
 * qpuf_verifier.ino - Q-PUF verifier running on the microcontroller (Arduino / ESP32 / STM32 core).
 * The PC simulator plays the PUF "device"; this board is the VERIFIER that holds the keys.
 *
 * Serial protocol, 115200 baud, one command per line (ASCII, hex in lower or upper case):
 *   PING                       -> PONG
 *   ENROLL <id> <key32hex>     -> ENROLLED <id>            (store a 16-byte key in slot id 0..3)
 *   CHAL <id>                  -> NONCE <32hex>            (fresh 16-byte random nonce, one-time use)
 *   RESP <id> <tag32hex>       -> OK <us>  |  FAIL <us>    (<us> = microseconds spent hashing)
 *   HASH <hexmsg>              -> DIGEST <64hex>           (self-test: Ascon-Hash of up to 64 bytes)
 */
#include "ascon_hash.h"

#define NSLOT 4
static uint8_t  keys[NSLOT][16];
static bool     key_ok[NSLOT];
static uint8_t  nonce[NSLOT][16];
static bool     nonce_ok[NSLOT];
static char     line[200];
static uint8_t  len = 0;

static int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}
static int parse_hex(const char *s, uint8_t *out, int maxbytes) {       // returns #bytes or -1
  int n = 0;
  while (s[0] && s[1] && n < maxbytes) {
    int a = hexval(s[0]), b = hexval(s[1]);
    if (a < 0 || b < 0) return -1;
    out[n++] = (uint8_t)((a << 4) | b); s += 2;
  }
  return n;
}
static void print_hex(const uint8_t *p, int n) {
  static const char H[] = "0123456789abcdef";
  for (int i = 0; i < n; i++) { Serial.print(H[p[i] >> 4]); Serial.print(H[p[i] & 15]); }
}
static void random_bytes(uint8_t *p, int n) {
#if defined(ESP32)
  for (int i = 0; i < n; i++) p[i] = (uint8_t)(esp_random() & 0xFF);     // hardware RNG
#else
  for (int i = 0; i < n; i++) p[i] = (uint8_t)random(256);               // seeded in setup()
#endif
}

static void handle(char *cmd) {
  char *tok = strtok(cmd, " ");
  if (!tok) return;
  if (!strcmp(tok, "PING")) { Serial.println("PONG"); return; }

  if (!strcmp(tok, "HASH")) {
    char *h = strtok(NULL, " "); uint8_t m[64], d[32];
    int n = h ? parse_hex(h, m, 64) : 0;
    if (n < 0) { Serial.println("ERR hex"); return; }
    ascon_hash(d, 32, m, n);
    Serial.print("DIGEST "); print_hex(d, 32); Serial.println(); return;
  }

  char *ids = strtok(NULL, " ");
  int id = ids ? atoi(ids) : -1;
  if (id < 0 || id >= NSLOT) { Serial.println("ERR id"); return; }

  if (!strcmp(tok, "ENROLL")) {
    char *h = strtok(NULL, " ");
    if (!h || parse_hex(h, keys[id], 16) != 16) { Serial.println("ERR key"); return; }
    key_ok[id] = true; nonce_ok[id] = false;
    Serial.print("ENROLLED "); Serial.println(id); return;
  }
  if (!strcmp(tok, "CHAL")) {
    if (!key_ok[id]) { Serial.println("ERR noenroll"); return; }
    random_bytes(nonce[id], 16); nonce_ok[id] = true;
    Serial.print("NONCE "); print_hex(nonce[id], 16); Serial.println(); return;
  }
  if (!strcmp(tok, "RESP")) {
    char *h = strtok(NULL, " "); uint8_t rx[16], exp[16];
    if (!key_ok[id] || !nonce_ok[id]) { Serial.println("FAIL 0"); return; }  // no open challenge
    if (!h || parse_hex(h, rx, 16) != 16) { Serial.println("ERR tag"); return; }
    nonce_ok[id] = false;                                   // nonce is single-use (anti-replay)
    unsigned long t0 = micros();
    qpuf_make_tag(exp, keys[id], nonce[id]);
    unsigned long us = micros() - t0;
    uint8_t diff = 0;
    for (int i = 0; i < 16; i++) diff |= exp[i] ^ rx[i];    // constant-time compare
    Serial.print(diff == 0 ? "OK " : "FAIL "); Serial.println(us); return;
  }
  Serial.println("ERR cmd");
}

void setup() {
  Serial.begin(115200);
#if !defined(ESP32)
  randomSeed(analogRead(A0) ^ micros());                    // weak seed: fine for a demo only
#endif
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') { line[len] = 0; len = 0; handle(line); }
    else if (len < sizeof(line) - 1) line[len++] = c;
  }
}
