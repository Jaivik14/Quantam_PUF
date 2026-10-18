`timescale 1ns/1ps
// Run:  vvp tb_fuzzy +REPFILE=rep_ber04.txt +ENRFILE=enroll_vectors.txt
module tb_fuzzy;
  localparam int KEY = 128, REP = 7, RAW = KEY*REP;
  logic clk = 0, rst_n = 0, start = 0, mode_enroll = 0, done;
  logic [RAW-1:0] puf_bits, helper_in, helper_out;
  logic [KEY-1:0] secret_in, secret_out;
  logic [15:0] err_est;
  fuzzy_extractor_top #(.KEY_BITS(KEY), .REP(REP)) dut (.*);
  always #5 clk = ~clk;

  string repfile, enrfile;
  integer fd, rc, tot = 0, bad = 0, errmis = 0, err_exp_i;
  logic [RAW-1:0] Rn, W, Rin, Wexp;
  logic [KEY-1:0] s_exp, s_in;

  task automatic pulse;
    @(posedge clk); start = 1; @(posedge clk); start = 0; @(posedge clk);
  endtask

  initial begin
    if (!$value$plusargs("REPFILE=%s", repfile)) repfile = "rep_ber04.txt";
    if (!$value$plusargs("ENRFILE=%s", enrfile)) enrfile = "enroll_vectors.txt";
    repeat (3) @(posedge clk); rst_n = 1;

    // ---- reproduce mode ----
    fd = $fopen(repfile, "r");
    if (fd == 0) begin $display("ERROR: cannot open %s", repfile); $finish; end
    mode_enroll = 0;
    while (!$feof(fd)) begin
      rc = $fscanf(fd, "%h %h %h %d\n", Rn, W, s_exp, err_exp_i);
      if (rc == 4) begin
        puf_bits = Rn; helper_in = W; pulse();
        tot++;
        if (secret_out !== s_exp) bad++;
        if (err_est !== err_exp_i[15:0]) errmis++;
      end
    end
    $fclose(fd);
    $display("REPRODUCE %-22s : %0d vectors, secret matches = %0d, key failures = %0d (%0.2f%%), err_est mismatches = %0d",
             repfile, tot, tot-bad, bad, 100.0*bad/tot, errmis);

    // ---- enroll mode ----
    fd = $fopen(enrfile, "r"); tot = 0; bad = 0; mode_enroll = 1;
    while (!$feof(fd)) begin
      rc = $fscanf(fd, "%h %h %h\n", Rin, s_in, Wexp);
      if (rc == 3) begin
        puf_bits = Rin; secret_in = s_in; pulse();
        tot++; if (helper_out !== Wexp) bad++;
      end
    end
    $display("ENROLL    %-22s : %0d vectors, helper-data errors = %0d -> %s", enrfile, tot, bad, bad == 0 ? "PASS" : "FAIL");
    $finish;
  end
endmodule
