// Chapter 24 testbench for sess: line k of out/sess_stim.hex (64 hex digits) is everything on the pins in cycle k, cycle 0 being the first cycle after reset: the request (held on the pins until the unit accepts it: model/sess_gold.py run() decides which cycle), bits 0..168 (valid, kind, token, new token, symbol, side, shares, price, tif); a server packet, bits 169..209 (valid, type, sequence number); a configuration write, bits 210..249 (valid, what, symbol, data). Before every clock edge it prints
//   C <cycle> <in_ready> <o_valid> <o_data hex> <o_last> <o_nb> <state> <expected seq> <answer valid> <answer>     (zeros when o_valid = 0)
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef W
`define W 8
`endif
`ifndef NS
`define NS 4
`endif
`ifndef HB
`define HB 20
`endif
`ifndef TL
`define TL 60
`endif
module sess_tb;
    localparam int NC = `NC, W = `W;
    logic clk = 0, rst = 1; logic [255:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic in_valid = 0, in_side = 0, rx_valid = 0, cfg_valid = 0; logic [2:0] in_kind = '0, cfg_what = '0; logic [31:0] in_tok = '0, in_tok2 = '0, in_shares = '0, in_px = '0, in_tif = '0, rx_seq = '0, cfg_data = '0; logic [3:0] in_sym = '0, cfg_sym = '0; logic [7:0] rx_type = '0;
    logic in_ready, o_valid, o_last, o_rv; logic [8*W-1:0] o_data; logic [3:0] o_nb; logic [2:0] o_state; logic [31:0] o_exp; logic [1:0] o_res;
    sess #(.W(W), .NS(`NS), .HB(`HB), .TL(`TL)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_kind(in_kind), .in_tok(in_tok), .in_tok2(in_tok2), .in_sym(in_sym), .in_side(in_side), .in_shares(in_shares), .in_px(in_px), .in_tif(in_tif), .in_ready(in_ready),
        .rx_valid(rx_valid), .rx_type(rx_type), .rx_seq(rx_seq), .cfg_valid(cfg_valid), .cfg_what(cfg_what), .cfg_sym(cfg_sym), .cfg_data(cfg_data),
        .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_nb(o_nb), .o_state(o_state), .o_exp(o_exp), .o_rv(o_rv), .o_res(o_res));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin   // Icarus only: every register powers up with garbage, so that a reset that forgets one is seen
        dut.st = 3'd2; dut.expseq = 32'd77; dut.hbc = 16'd9; dut.rxc = 16'd9; dut.ltc = 16'd9; dut.tx = {256{1'b1}}; dut.txlen = 6'd9; dut.rv = 1'b1; dut.res = 2'd2;
        for (int i = 0; i < `NS; i++) dut.stock[i] = 32'hDEADBEEF; dut.user = 32'h11111111; dut.pw = 32'h22222222; dut.firm = 32'h33333333; dut.reqseq = 32'h44444444; dut.display = 8'h55; dut.capacity = 8'h66;
    end
`endif
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0h %0d %0d %0d %0d %0d %0d", cyc, in_ready, o_valid, o_valid ? o_data : '0, o_valid ? o_last : 1'b0, o_valid ? o_nb : 4'd0, o_state, o_exp, o_rv, o_rv ? o_res : 2'd0);
        cyc++;
    end
    initial begin
        $readmemh("out/sess_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            in_valid = vec[k][0]; in_kind = vec[k][3:1]; in_tok = vec[k][35:4]; in_tok2 = vec[k][67:36]; in_sym = vec[k][71:68]; in_side = vec[k][72]; in_shares = vec[k][104:73]; in_px = vec[k][136:105]; in_tif = vec[k][168:137];
            rx_valid = vec[k][169]; rx_type = vec[k][177:170]; rx_seq = vec[k][209:178]; cfg_valid = vec[k][210]; cfg_what = vec[k][213:211]; cfg_sym = vec[k][217:214]; cfg_data = vec[k][249:218];
            run = 1; @(negedge clk);
        end
        in_valid = 0; rx_valid = 0; cfg_valid = 0; repeat (8) @(negedge clk); $finish;
    end
endmodule
