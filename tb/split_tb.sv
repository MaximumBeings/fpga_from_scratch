// Chapter 15 testbench for tcp_split: replays out/split_stim.hex, one line per clock cycle (the event offered, the pop of the punt FIFO, the write-back from software; see model/split_gold.py write_stim). Before every edge it prints
//   C <ev_ready> <r_valid> <r_cid> <r_path> <r_txv> <r_txf> <r_txseq> <r_txack> <r_dlv> <pq_valid> <pq_data in hex, or - when the FIFO is empty>
// which model/split_gold.py predicts cycle for cycle.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef CIDW
`define CIDW 2
`endif
`ifndef DEPTH
`define DEPTH 4
`endif
`ifndef POLICY
`define POLICY 0
`endif
module split_tb;
    localparam int NC = `NC, CW = `CIDW, PWID = CW + 237;
    logic clk = 0, rst = 1; logic [267:0] vec [0:NC-1]; int k = 0;
    logic ev_valid = 0, pq_pop = 0, wb_valid = 0, wb_pas = 0; logic [CW-1:0] ev_cid = '0, wb_cid = '0; logic [2:0] ev_type = '0; logic [3:0] ev_f = '0, wb_st = '0; logic [31:0] ev_seq = '0, ev_ack = '0, ev_iss = '0, wb_una = '0, wb_nxt = '0, wb_rcv = '0; logic [15:0] ev_ln = '0, ev_wnd = '0;
    logic ev_ready, r_valid, r_txv, pq_valid; logic [CW-1:0] r_cid; logic [1:0] r_path; logic [3:0] r_txf; logic [31:0] r_txseq, r_txack; logic [15:0] r_dlv; logic [PWID-1:0] pq_data;
    tcp_split #(.CIDW(CW), .DEPTH(`DEPTH), .POLICY(`POLICY)) dut (.clk(clk), .rst(rst), .ev_valid(ev_valid), .ev_cid(ev_cid), .ev_type(ev_type), .ev_f(ev_f), .ev_seq(ev_seq), .ev_ack(ev_ack), .ev_ln(ev_ln), .ev_wnd(ev_wnd), .ev_iss(ev_iss), .ev_ready(ev_ready),
        .r_valid(r_valid), .r_cid(r_cid), .r_path(r_path), .r_txv(r_txv), .r_txf(r_txf), .r_txseq(r_txseq), .r_txack(r_txack), .r_dlv(r_dlv), .pq_valid(pq_valid), .pq_data(pq_data), .pq_pop(pq_pop),
        .wb_valid(wb_valid), .wb_cid(wb_cid), .wb_st(wb_st), .wb_pas(wb_pas), .wb_una(wb_una), .wb_nxt(wb_nxt), .wb_rcv(wb_rcv));
    always #4 clk = ~clk;
    logic run = 0; int nprint = 0;
    always @(posedge clk) if (run && nprint < NC) begin
        if (pq_valid) $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %h", ev_ready, r_valid, r_valid ? r_cid : '0, r_path, r_txv, r_txf, r_txseq, r_txack, r_dlv, pq_valid, pq_data);
        else $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d -", ev_ready, r_valid, r_valid ? r_cid : '0, r_path, r_txv, r_txf, r_txseq, r_txack, r_dlv, pq_valid);
        nprint++;
    end
    initial begin
        $readmemh("out/split_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            ev_valid = vec[k][264]; ev_cid = vec[k][256 +: CW]; ev_type = vec[k][254:252]; ev_f = vec[k][251:248]; ev_seq = vec[k][247:216]; ev_ack = vec[k][215:184]; ev_ln = vec[k][183:168]; ev_wnd = vec[k][167:152]; ev_iss = vec[k][151:120];
            pq_pop = vec[k][116]; wb_valid = vec[k][112]; wb_cid = vec[k][104 +: CW]; wb_st = vec[k][103:100]; wb_pas = vec[k][96]; wb_una = vec[k][95:64]; wb_nxt = vec[k][63:32]; wb_rcv = vec[k][31:0];
            run = 1; @(negedge clk);
        end
        $display("DONE"); $finish;
    end
endmodule
