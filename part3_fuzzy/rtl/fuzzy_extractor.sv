// fuzzy_extractor.sv - code-offset fuzzy extractor with a repetition code (combinational core).
//   mode_enroll = 1 :  helper_out = puf_bits ^ Rep(secret_in)
//   mode_enroll = 0 :  secret_out = majority per REP-bit group of (puf_bits ^ helper_in)
// err_est = number of raw bits the decoder corrected (a free "BER monitor").
module fuzzy_extractor #(
  parameter int KEY_BITS = 128,
  parameter int REP      = 7                 // odd number
)(
  input  logic                        mode_enroll,
  input  logic [KEY_BITS*REP-1:0]     puf_bits,      // R (enroll) or R' (reproduce)
  input  logic [KEY_BITS-1:0]         secret_in,     // enroll only
  input  logic [KEY_BITS*REP-1:0]     helper_in,     // reproduce only
  output logic [KEY_BITS*REP-1:0]     helper_out,    // enroll result
  output logic [KEY_BITS-1:0]         secret_out,    // reproduce result
  output logic [15:0]                 err_est
);
  localparam int RAW = KEY_BITS * REP;
  logic [RAW-1:0] rep_code, noisy;
  assign noisy = puf_bits ^ helper_in;

  genvar i;
  generate
    for (i = 0; i < KEY_BITS; i++) begin : g_rep
      assign rep_code[RAW-1-i*REP -: REP] = {REP{secret_in[KEY_BITS-1-i]}};
    end
  endgenerate
  assign helper_out = puf_bits ^ rep_code;

  always_comb begin
    int ones, e;
    err_est = '0;
    for (int g = 0; g < KEY_BITS; g++) begin
      ones = 0;
      for (int b = 0; b < REP; b++) ones += int'(noisy[RAW-1-g*REP-b]);
      secret_out[KEY_BITS-1-g] = (ones > REP/2);
      e = (ones > REP/2) ? (REP - ones) : ones;
      err_est += 16'(e);
    end
  end
endmodule
