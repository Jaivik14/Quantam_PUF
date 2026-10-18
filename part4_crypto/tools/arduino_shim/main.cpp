#include "Arduino.h"
#include "../../firmware/qpuf_verifier/qpuf_verifier.ino"
int main() { setup(); while (!Serial.eof) loop(); return 0; }
