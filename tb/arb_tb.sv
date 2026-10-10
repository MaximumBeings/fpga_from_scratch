// Chapter 18 testbench for seq_arb: line k of out/arb_stim.hex is the input OFFERED in cycle k: valid(bit 50) feed(49:48) seq(47:16) cnt(15:0), 13 hex digits (junk where valid = 0). The packet is held on the pins whether or not the design is ready: model/arb_gold.py run() decides which cycle's offer is accepted. Before every clock edge it prints one line
//   C <cycle> <in_ready> <d_valid> <d_kind> <d_seq> <d_cnt> <d_feed> <t_valid> <t_kind> <t_seq> <t_cnt> <next> <slots in use>
// where the d_ and t_ fields are those registered at the previous edge (zero when not valid) and next / slots are the state before this cycle.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef PEND
`define PEND 4
`endif
`ifndef TO
`define TO 16
`endif
`ifndef TO2
`define TO2 64
`endif
`ifndef INIT
`define INIT 1
`endif
module arb_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, in_valid = 0; logic [1:0] in_feed = '0; logic [31:0] in_seq = '0; logic [15:0] in_cnt = '0; logic [51:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic in_ready, d_valid, t_valid; logic [2:0] d_kind; logic [31:0] d_seq, t_seq, t_cnt, o_next; logic [15:0] d_cnt; logic [1:0] d_feed, t_kind; logic [3:0] o_np;
    seq_arb #(.PEND(`PEND), .TO(`TO), .TO2(`TO2), .INIT(32'(`INIT))) dut (.clk(clk), .rst(rst), .in_valid(in_valid), .in_feed(in_feed), .in_seq(in_seq), .in_cnt(in_cnt), .in_ready(in_ready), .d_valid(d_valid), .d_kind(d_kind), .d_seq(d_seq), .d_cnt(d_cnt), .d_feed(d_feed),
        .t_valid(t_valid), .t_kind(t_kind), .t_seq(t_seq), .t_cnt(t_cnt), .o_next(o_next), .o_np(o_np));
    always #4 clk = ~clk;
`ifdef GARBAGE
    initial begin for (int i = 0; i < `PEND; i++) begin dut.sv[i] = 1'b1; dut.sd[i] = 32'h12345678 + i; dut.sc[i] = 16'd9; dut.sf[i] = 2'd1; end dut.nx = 32'hdeadbeef; dut.tmr = 16'd3; dut.req = 1'b1; end   // Icarus only: the registers power up with garbage, so that a reset that forgets one is seen
`endif
    always @(posedge clk) if (run) begin
        $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d", cyc, in_ready, d_valid, d_valid ? d_kind : 3'd0, d_valid ? d_seq : 32'd0, d_valid ? d_cnt : 16'd0, d_valid ? d_feed : 2'd0, t_valid, t_valid ? t_kind : 2'd0, t_valid ? t_seq : 32'd0, t_valid ? t_cnt : 32'd0, o_next, o_np);
        cyc++;
    end
    initial begin
        $readmemh("out/arb_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            in_valid = vec[k][50]; in_feed = vec[k][49:48]; in_seq = vec[k][47:16]; in_cnt = vec[k][15:0]; run = 1; @(negedge clk);
        end
        in_valid = 0; repeat (3) @(negedge clk); $finish;
    end
endmodule
