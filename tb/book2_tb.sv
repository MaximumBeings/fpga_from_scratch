// Chapter 20 testbench for book2: line k of out/book2_stim.hex is the event OFFERED in cycle k: valid(1) type(1) sym(1) side(1) ref(8) ref2(8) px(8) sh(8) hex digits (junk where valid = 0); the offer is held on the pins whether or not the engine is ready: model/book_gold.py run() decides which cycle's offer is accepted. Before every clock edge it prints
//   C <cycle> <in_ready> <o_valid> <result> <symbol> <best bid px> <bid sh> <best ask px> <ask sh> <bid levels> <ask levels> <orders>
// (zeros when o_valid = 0): the result registered at the previous edge and the top of book of its symbol read from the level registers now.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef NS
`define NS 2
`endif
`ifndef D
`define D 4
`endif
`ifndef NB
`define NB 4
`endif
`ifndef K
`define K 2
`endif
module book2_tb;
    localparam int NC = `NC, SW = (`NS > 1) ? $clog2(`NS) : 1;
    logic clk = 0, rst = 1, in_valid = 0, in_side = 0; logic [2:0] in_type = '0; logic [31:0] in_ref = '0, in_ref2 = '0, in_px = '0, in_sh = '0; logic [SW-1:0] in_sym = '0; logic [143:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic in_ready, o_valid; logic [2:0] o_res; logic [SW-1:0] o_sym; logic [31:0] o_bpx, o_bsh, o_apx, o_ash; logic [7:0] o_bn, o_an; logic [15:0] o_nord;
    book2 #(.NS(`NS), .D(`D), .NB(`NB), .K(`K)) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_type(in_type), .in_ref(in_ref), .in_ref2(in_ref2), .in_sym(in_sym), .in_side(in_side), .in_px(in_px), .in_sh(in_sh), .in_ready(in_ready),
        .o_valid(o_valid), .o_res(o_res), .o_sym(o_sym), .o_bpx(o_bpx), .o_bsh(o_bsh), .o_apx(o_apx), .o_ash(o_ash), .o_bn(o_bn), .o_an(o_an), .o_nord(o_nord));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin   // Icarus only: the registers and both RAMs power up with garbage, so that a reset or a clearing sweep that forgets something is seen
        dut.nord = 16'd7; for (int i = 0; i < `NB * `K; i++) dut.om[i] = '1; for (int i = 0; i < `NS * 2 * `D; i++) dut.lm[i] = 64'h0000004d00000003;
        for (int s = 0; s < `NS * 2; s++) begin dut.cnt[s] = 3; dut.tpx[s] = 32'd77; dut.tsh[s] = 32'd5; end
    end
`endif
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc, in_ready, o_valid, o_valid ? o_res : 3'd0, o_valid ? o_sym : '0, o_valid ? o_bpx : 32'd0, o_valid ? o_bsh : 32'd0, o_valid ? o_apx : 32'd0, o_valid ? o_ash : 32'd0, o_valid ? o_bn : 8'd0, o_valid ? o_an : 8'd0, o_valid ? o_nord : 16'd0);
        cyc++;
    end
    initial begin
        $readmemh("out/book2_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            in_valid = vec[k][140]; in_type = vec[k][138:136]; in_sym = vec[k][132 +: SW]; in_side = vec[k][128]; in_ref = vec[k][127:96]; in_ref2 = vec[k][95:64]; in_px = vec[k][63:32]; in_sh = vec[k][31:0]; run = 1; @(negedge clk);
        end
        in_valid = 0; repeat (3) @(negedge clk); $finish;
    end
endmodule
