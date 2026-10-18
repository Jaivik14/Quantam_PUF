`timescale 1ns/1ps
module tb_qpuf_auth_unit;
  logic clk = 0, rst_n = 0, start = 0, busy, done;
  logic [127:0] secret, nonce, key, tag;
  qpuf_auth_unit dut (.*);
  always #5 clk = ~clk;
  integer fd, rc, errors = 0, total = 0, cyc;
  logic [127:0] s_in, n_in, k_exp, t_exp;
  initial begin
    fd = $fopen("auth_vectors.txt", "r");
    if (fd == 0) begin $display("ERROR: cannot open auth_vectors.txt"); $finish; end
    repeat (3) @(posedge clk); rst_n = 1; @(posedge clk);
    while (!$feof(fd)) begin
      rc = $fscanf(fd, "%h %h %h %h\n", s_in, n_in, k_exp, t_exp);
      if (rc == 4) begin
        secret = s_in; nonce = n_in;
        @(posedge clk); start = 1; @(posedge clk); start = 0; cyc = 0;
        while (!done) begin @(posedge clk); cyc++; end
        total++;
        if (key !== k_exp || tag !== t_exp) begin
          errors++; $display("MISMATCH key %h/%h tag %h/%h", key, k_exp, tag, t_exp);
        end
        @(posedge clk);
      end
    end
    $display("qpuf_auth_unit: %0d vectors, %0d errors, %0d cycles per auth -> %s",
             total, errors, cyc + 1, errors == 0 ? "PASS" : "FAIL");
    $finish;
  end
endmodule
