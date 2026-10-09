// Chapter 10 testbench for the match engines: replays out/match_stim.hex, one operation per cycle: type (0 idle, 1 write, 2 query), sel, addr, key, aux, val, vld (25 hex digits). Idle cycles carry random junk on every field (a don't-care must be ignored). Prints `RES <hit> <val>` for each result (val is 0 on a miss), `LAT` (cycles from the first query to its result) and `DONE`. Defines: NC (cycles), ENG (0 exact CAM, 1 TCAM, 2 range, 3 hash with one table, 4 hash with two tables), N (CAM entries), AW (hash address bits), KW (stored key bits).
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef ENG
`define ENG 0
`endif
`ifndef N
`define N 16
`endif
`ifndef AW
`define AW 8
`endif
`ifndef KW
`define KW 32
`endif
module match_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, q_valid = 0, w_en = 0, w_sel = 0, w_vld = 0; logic [31:0] q_key = '0, w_key = '0, w_aux = '0; logic [11:0] w_addr = '0; logic [7:0] w_val = '0; logic r_valid, r_hit; logic [7:0] r_val;
    logic [99:0] vec [0:NC-1]; int k, nres = 0, cyc = 0, first_q = -1, first_r = -1;
    if (`ENG < 3) begin : gc
        match_cam #(.N(`N), .MODE(`ENG)) dut (.clk(clk), .rst(rst), .q_valid(q_valid), .q_key(q_key), .w_en(w_en), .w_sel(w_sel), .w_addr(w_addr), .w_key(w_key), .w_aux(w_aux), .w_val(w_val), .w_vld(w_vld), .r_valid(r_valid), .r_hit(r_hit), .r_val(r_val));
    end else begin : gh
        hash_tab #(.AW(`AW), .CH(`ENG - 2), .KW(`KW)) dut (.clk(clk), .rst(rst), .q_valid(q_valid), .q_key(q_key), .w_en(w_en), .w_sel(w_sel), .w_addr(w_addr), .w_key(w_key), .w_aux(w_aux), .w_val(w_val), .w_vld(w_vld), .r_valid(r_valid), .r_hit(r_hit), .r_val(r_val));
    end
    if (`ENG < 3) begin : gi
        initial begin gc.dut.vld = '1; for (int i = 0; i < `N; i++) begin gc.dut.k[i] = 32'd0; gc.dut.a[i] = 32'd0; gc.dut.v[i] = 8'h5A; end end         // power-up garbage: every slot looks valid; only the reset can empty the CAM
    end
    always #4 clk = ~clk;
    always @(posedge clk) begin
        cyc <= cyc + 1; if (q_valid && !rst && first_q < 0) first_q = cyc;
        if (r_valid) begin $display("RES %0d %0d", r_hit, r_val); nres++; if (first_r < 0) first_r = cyc; end
    end
    initial begin
        $readmemh("out/match_stim.hex", vec);
        q_valid = 1; w_en = 1; repeat (3) @(negedge clk); rst = 0; q_valid = 0; w_en = 0;       // valid inputs during reset: reset must discard them (the queries; the writes are the model's business)
        for (k = 0; k < NC; k++) begin
            @(negedge clk);
            q_valid = (vec[k][99:96] == 4'd2); w_en = (vec[k][99:96] == 4'd1); w_sel = vec[k][92]; w_addr = vec[k][87:76]; q_key = vec[k][75:44]; w_key = vec[k][75:44]; w_aux = vec[k][43:12]; w_val = vec[k][11:4]; w_vld = vec[k][0];
        end
        @(negedge clk); q_valid = 0; w_en = 0; repeat (6) @(negedge clk); $display("LAT %0d", first_r - first_q); $display("DONE %0d results", nres); $finish;
    end
endmodule
