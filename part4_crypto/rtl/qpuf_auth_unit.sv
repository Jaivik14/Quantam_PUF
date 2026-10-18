// qpuf_auth_unit.sv - key derivation + authentication tag from the fuzzy-extractor secret.
//   key = Ascon-Hash("QPUF-KEY" || secret)[127:0]        (first 16 bytes of the digest)
//   tag = Ascon-Hash(key || nonce)[127:0]
// Re-uses ONE ascon_hash_core twice (area-efficient, ~2 x 119 clock cycles).
module qpuf_auth_unit (
  input  logic         clk, rst_n,
  input  logic         start,
  input  logic [127:0] secret,      // from the fuzzy extractor (byte 0 = bits 127:120)
  input  logic [127:0] nonce,       // from the verifier
  output logic         busy, done,
  output logic [127:0] key,
  output logic [127:0] tag
);
  typedef enum logic [2:0] {A_IDLE, A_KDF_GO, A_KDF_WAIT, A_TAG_GO, A_TAG_WAIT, A_DONE} st_t;
  st_t st;
  logic        h_start, h_busy, h_done;
  logic [255:0] h_msg, h_digest;
  logic [5:0]  h_len;
  logic [127:0] secret_q, nonce_q;

  ascon_hash_core u_hash (.clk, .rst_n, .start(h_start), .msg(h_msg), .msg_len(h_len),
                          .busy(h_busy), .done(h_done), .digest(h_digest));

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      st <= A_IDLE; h_start <= 1'b0; h_msg <= '0; h_len <= '0;
      key <= '0; tag <= '0; busy <= 1'b0; done <= 1'b0; secret_q <= '0; nonce_q <= '0;
    end else begin
      h_start <= 1'b0; done <= 1'b0;
      case (st)
        A_IDLE: if (start) begin
          secret_q <= secret; nonce_q <= nonce; busy <= 1'b1; st <= A_KDF_GO;
        end
        A_KDF_GO: begin
          h_msg <= {64'h515055462d4b4559, secret_q, 64'd0};    // "QPUF-KEY" || secret
          h_len <= 6'd24;  h_start <= 1'b1;  st <= A_KDF_WAIT;
        end
        A_KDF_WAIT: if (h_done) begin key <= h_digest[255:128]; st <= A_TAG_GO; end
        A_TAG_GO: begin
          h_msg <= {key, nonce_q};                             // key || nonce
          h_len <= 6'd32;  h_start <= 1'b1;  st <= A_TAG_WAIT;
        end
        A_TAG_WAIT: if (h_done) begin tag <= h_digest[255:128]; st <= A_DONE; end
        A_DONE: begin done <= 1'b1; busy <= 1'b0; st <= A_IDLE; end
        default: st <= A_IDLE;
      endcase
    end
  end
endmodule
