`timescale 1ns/1ps
module tb_ascon_hash_core;
  logic clk = 0, rst_n = 0, start = 0;
  logic [255:0] msg, digest;
  logic [5:0] msg_len;
  logic busy, done;
  ascon_hash_core dut (.*);
  always #5 clk = ~clk;                                   // 100 MHz

  integer fd, rc, len, errors = 0, total = 0, cycles;
  logic [255:0] m_in, d_exp;
  initial begin
    fd = $fopen("hash_vectors.txt", "r");
    if (fd == 0) begin $display("ERROR: cannot open hash_vectors.txt"); $finish; end
    repeat (3) @(posedge clk);  rst_n = 1;  @(posedge clk);
    while (!$feof(fd)) begin
      rc = $fscanf(fd, "%d %h %h\n", len, m_in, d_exp);
      if (rc == 3) begin
        msg = m_in; msg_len = len[5:0];
        @(posedge clk); start = 1; @(posedge clk); start = 0;
        cycles = 0;
        while (!done) begin @(posedge clk); cycles++; end
        total++;
        if (digest !== d_exp) begin
          errors++; $display("MISMATCH len=%0d got %h exp %h", len, digest, d_exp);
        end
        if (len == 32) $display("len=32 bytes -> %0d clock cycles", cycles + 1);
        @(posedge clk);
      end
    end
    $display("ascon_hash_core: %0d vectors, %0d errors  -> %s", total, errors, errors == 0 ? "PASS" : "FAIL");
    $finish;
  end
endmodule
