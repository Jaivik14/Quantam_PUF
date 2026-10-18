// ascon_hash_core.sv - iterative Ascon-Hash (v1.2, 256-bit digest), 1 round per clock.
// Message: up to 32 bytes. Byte 0 of the message is msg[255:248] (big-endian, same as Python/C).
module ascon_hash_core (
  input  logic         clk,
  input  logic         rst_n,
  input  logic         start,        // 1-cycle pulse, only honoured while idle
  input  logic [255:0] msg,          // message bytes, byte 0 at the top
  input  logic [5:0]   msg_len,      // 0..32 bytes
  output logic         busy,
  output logic         done,         // 1-cycle pulse when digest is valid
  output logic [255:0] digest        // byte 0 of digest at the top
);
  localparam logic [63:0] IV = 64'h00400c0000000100;

  typedef enum logic [2:0] {S_IDLE, S_PERM, S_ABSORB, S_SQUEEZE, S_DONE} state_t;
  typedef enum logic       {AP_ABSORB, AP_SQUEEZE} after_t;

  state_t        state;
  after_t        after_perm;
  logic [63:0]   x0, x1, x2, x3, x4;     // 320-bit Ascon state
  logic [3:0]    rnd;                    // round counter 0..11
  logic [2:0]    blk;                    // absorb block index 0..4
  logic [1:0]    sq;                     // squeeze word index 0..3
  logic [255:0]  msg_q;
  logic [5:0]    len_q;

  wire [2:0]  n_full = len_q[5:3];       // number of full 8-byte blocks (0..4)
  wire [2:0]  r_byte = len_q[2:0];       // bytes in the final partial block (0..7)
  wire [319:0] msg_ext = {msg_q, 64'd0}; // block 4 reads as zero

  // final block = remaining message bytes, then 0x80, then zeros
  wire [63:0] raw_last  = msg_ext[319 - 64*n_full -: 64];
  wire [63:0] keep_mask = (r_byte == 3'd0) ? 64'd0 : ~(64'hFFFF_FFFF_FFFF_FFFF >> (8*r_byte));
  wire [63:0] last_word = (raw_last & keep_mask) | (64'h8000_0000_0000_0000 >> (8*r_byte));
  wire [63:0] full_word = msg_ext[319 - 64*blk -: 64];

  // round constants: f0, e1, d2, c3, b4, a5, 96, 87, 78, 69, 5a, 4b
  wire [7:0] rc = 8'hf0 - {rnd, 4'b0000} + {4'b0000, rnd};   // = 0xf0 - 0x0f*rnd

  function automatic logic [319:0] ascon_round(input logic [319:0] st, input logic [7:0] c);
    logic [63:0] a0, a1, a2, a3, a4, t0, t1, t2, t3, t4;
    {a0, a1, a2, a3, a4} = st;
    a2 = a2 ^ {56'd0, c};                                      // add round constant
    a0 = a0 ^ a4;  a4 = a4 ^ a3;  a2 = a2 ^ a1;                // substitution layer
    t0 = ~a0 & a1; t1 = ~a1 & a2; t2 = ~a2 & a3; t3 = ~a3 & a4; t4 = ~a4 & a0;
    a0 = a0 ^ t1;  a1 = a1 ^ t2;  a2 = a2 ^ t3;  a3 = a3 ^ t4;  a4 = a4 ^ t0;
    a1 = a1 ^ a0;  a0 = a0 ^ a4;  a3 = a3 ^ a2;  a2 = ~a2;
    a0 = a0 ^ {a0[18:0], a0[63:19]} ^ {a0[27:0], a0[63:28]};   // ror 19, 28
    a1 = a1 ^ {a1[60:0], a1[63:61]} ^ {a1[38:0], a1[63:39]};   // ror 61, 39
    a2 = a2 ^ {a2[0:0],  a2[63:1]}  ^ {a2[5:0],  a2[63:6]};    // ror 1, 6
    a3 = a3 ^ {a3[9:0],  a3[63:10]} ^ {a3[16:0], a3[63:17]};   // ror 10, 17
    a4 = a4 ^ {a4[6:0],  a4[63:7]}  ^ {a4[40:0], a4[63:41]};   // ror 7, 41
    return {a0, a1, a2, a3, a4};
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= S_IDLE; after_perm <= AP_ABSORB;
      {x0, x1, x2, x3, x4} <= '0;
      rnd <= '0; blk <= '0; sq <= '0; msg_q <= '0; len_q <= '0;
      busy <= 1'b0; done <= 1'b0; digest <= '0;
    end else begin
      done <= 1'b0;
      case (state)
        S_IDLE: if (start) begin
          msg_q <= msg;  len_q <= msg_len;
          {x0, x1, x2, x3, x4} <= {IV, 256'd0};
          rnd <= 4'd0; blk <= 3'd0; sq <= 2'd0;
          after_perm <= AP_ABSORB;  state <= S_PERM;  busy <= 1'b1;
        end

        S_PERM: begin                                   // one Ascon round per clock
          {x0, x1, x2, x3, x4} <= ascon_round({x0, x1, x2, x3, x4}, rc);
          if (rnd == 4'd11) begin
            rnd   <= 4'd0;
            state <= (after_perm == AP_ABSORB) ? S_ABSORB : S_SQUEEZE;
          end else rnd <= rnd + 4'd1;
        end

        S_ABSORB: begin
          if (blk < n_full) begin                       // full block: xor, then permute
            x0 <= x0 ^ full_word;  blk <= blk + 3'd1;
            after_perm <= AP_ABSORB;  state <= S_PERM;
          end else begin                                // last block: xor only, then squeeze
            x0 <= x0 ^ last_word;
            after_perm <= AP_SQUEEZE; state <= S_PERM;
          end
        end

        S_SQUEEZE: begin                                // reached after each permutation
          digest[255 - 64*sq -: 64] <= x0;
          if (sq == 2'd3) state <= S_DONE;
          else begin sq <= sq + 2'd1; after_perm <= AP_SQUEEZE; state <= S_PERM; end
        end

        S_DONE: begin done <= 1'b1; busy <= 1'b0; state <= S_IDLE; end
        default: state <= S_IDLE;
      endcase
    end
  end
endmodule
