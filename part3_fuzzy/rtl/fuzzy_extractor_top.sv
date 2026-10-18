// fuzzy_extractor_top.sv - registers the combinational core (1-cycle latency, FPGA-friendly timing).
module fuzzy_extractor_top #(
  parameter int KEY_BITS = 128,
  parameter int REP      = 7
)(
  input  logic                        clk, rst_n,
  input  logic                        start,
  input  logic                        mode_enroll,
  input  logic [KEY_BITS*REP-1:0]     puf_bits,
  input  logic [KEY_BITS-1:0]         secret_in,
  input  logic [KEY_BITS*REP-1:0]     helper_in,
  output logic                        done,
  output logic [KEY_BITS*REP-1:0]     helper_out,
  output logic [KEY_BITS-1:0]         secret_out,
  output logic [15:0]                 err_est
);
  logic [KEY_BITS*REP-1:0] h_c;  logic [KEY_BITS-1:0] s_c;  logic [15:0] e_c;
  fuzzy_extractor #(.KEY_BITS(KEY_BITS), .REP(REP)) u_core (
    .mode_enroll, .puf_bits, .secret_in, .helper_in,
    .helper_out(h_c), .secret_out(s_c), .err_est(e_c));

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin done <= 1'b0; helper_out <= '0; secret_out <= '0; err_est <= '0; end
    else begin
      done <= start;
      if (start) begin helper_out <= h_c; secret_out <= s_c; err_est <= e_c; end
    end
  end
endmodule
