// Chapter 21 testbench for trig: line k of out/trig_stim.hex (68 hex digits) is everything offered in cycle k, cycle 0 being the first cycle after reset (the table is cleared in cycles 0 to NB - 1): message bits 0..100 (valid, type, side, key, price, shares), rule write bits 101..217 (valid, rule, en, neg, type mask, symany, sideany, side, price op, shares op, symbol mask, price value, shares value), table write bits 218..268 (valid, address, key, index, valid bit); fields not offered are junk. Before every clock edge it prints
//   C <cycle> <ready> <o_valid> <found> <idx> <mask> <fire> <first>     (zeros when o_valid = 0)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef NB
`define NB 8
`endif
`ifndef K
`define K 2
`endif
`ifndef R
`define R 4
`endif
`ifndef PIPE
`define PIPE 0
`endif
module trig_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1; logic [271:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic in_valid = 0, in_side = 0, cfg_valid = 0, cfg_en = 0, cfg_neg = 0, cfg_symany = 0, cfg_sideany = 0, cfg_side = 0, ld_valid = 0, ld_val = 0;
    logic [2:0] in_type = '0, cfg_pxop = '0, cfg_shop = '0; logic [3:0] cfg_rule = '0; logic [4:0] cfg_tmask = '0, ld_idx = '0; logic [11:0] ld_addr = '0;
    logic [31:0] in_key = '0, in_px = '0, in_sh = '0, cfg_symmask = '0, cfg_pxval = '0, cfg_shval = '0, ld_key = '0;
    logic o_ready, o_valid, o_found, o_fire; logic [4:0] o_idx; logic [`R-1:0] o_mask; logic [3:0] o_first;
    trig #(.NB(`NB), .K(`K), .R(`R), .PIPE(`PIPE)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_type(in_type), .in_key(in_key), .in_side(in_side), .in_px(in_px), .in_sh(in_sh),
        .cfg_valid(cfg_valid), .cfg_rule(cfg_rule), .cfg_en(cfg_en), .cfg_neg(cfg_neg), .cfg_tmask(cfg_tmask), .cfg_symany(cfg_symany), .cfg_sideany(cfg_sideany), .cfg_side(cfg_side), .cfg_pxop(cfg_pxop), .cfg_shop(cfg_shop), .cfg_symmask(cfg_symmask), .cfg_pxval(cfg_pxval), .cfg_shval(cfg_shval),
        .ld_valid(ld_valid), .ld_addr(ld_addr), .ld_key(ld_key), .ld_idx(ld_idx), .ld_val(ld_val),
        .o_ready(o_ready), .o_valid(o_valid), .o_found(o_found), .o_idx(o_idx), .o_mask(o_mask), .o_fire(o_fire), .o_first(o_first));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin   // Icarus only: the rule registers and the table banks power up with garbage, so that a reset or a clearing sweep that forgets something is seen
        for (int r = 0; r < `R; r++) begin dut.r_en[r] = 1'b1; dut.r_neg[r] = 1'b0; dut.r_tmask[r] = 5'd31; dut.r_symany[r] = 1'b1; dut.r_sideany[r] = 1'b1; dut.r_pxop[r] = 3'd0; dut.r_shop[r] = 3'd0; end
        for (int i = 0; i < `NB; i++) begin
            if (`K > 0) dut.way[0].mem[i] = '1; if (`K > 1) dut.way[1].mem[i] = '1; if (`K > 2) dut.way[2].mem[i] = '1; if (`K > 3) dut.way[3].mem[i] = '1;
        end
    end
`endif
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d", cyc, o_ready, o_valid, o_valid ? o_found : 1'b0, o_valid ? o_idx : 5'd0, o_valid ? o_mask : '0, o_valid ? o_fire : 1'b0, o_valid ? o_first : 4'd0);
        cyc++;
    end
    initial begin
        $readmemh("out/trig_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            in_valid = vec[k][0]; in_type = vec[k][3:1]; in_side = vec[k][4]; in_key = vec[k][36:5]; in_px = vec[k][68:37]; in_sh = vec[k][100:69];
            cfg_valid = vec[k][101]; cfg_rule = vec[k][105:102]; cfg_en = vec[k][106]; cfg_neg = vec[k][107]; cfg_tmask = vec[k][112:108]; cfg_symany = vec[k][113]; cfg_sideany = vec[k][114]; cfg_side = vec[k][115]; cfg_pxop = vec[k][118:116]; cfg_shop = vec[k][121:119]; cfg_symmask = vec[k][153:122]; cfg_pxval = vec[k][185:154]; cfg_shval = vec[k][217:186];
            ld_valid = vec[k][218]; ld_addr = vec[k][230:219]; ld_key = vec[k][262:231]; ld_idx = vec[k][267:263]; ld_val = vec[k][268];
            run = 1; @(negedge clk);
        end
        in_valid = 0; cfg_valid = 0; ld_valid = 0; repeat (8) @(negedge clk); $finish;
    end
endmodule
