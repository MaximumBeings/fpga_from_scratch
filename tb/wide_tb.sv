// Chapter 17 testbench for the W-bytes-per-beat parser (rtl/mold_wide.sv; WB = bytes per beat): line k of out/wide_stim.hex is presented in cycle k, as the hex number {valid, sop, eop, rst, nb[3:0], data[8*WB-1:0]} (2*WB + 2 digits); a line with valid = 0 carries random junk in the other fields. Before every clock edge it prints the outputs that are valid:
//   M <cycle> <type> <err> <idx> <seq> <fields...>     the first block completing in a beat (the print statement is out/wide_print.vh, written by tools/gen_parser_wide.py)
//   X <cycle> <idx>                                    a second block completing in the same beat: framing error, packet abandoned
//   P <cycle> <trunc> <cntbad> <session> <count>       the packet ended
// <cycle> is the cycle number of the clock edge at which the output is seen (the line of the beat is cycle c, its outputs appear at cycle c + 1).
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
`ifndef WB
`define WB 8
`endif
module wide_tb;
    localparam int NC = `NC, WB = `WB, LW = 8 * WB + 8;
    logic clk = 0, rst = 1, valid = 0, sop = 0, eop = 0; logic [3:0] nb = '0; logic [8*WB-1:0] data = '0; logic [LW-1:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic m_valid, x_valid, p_valid, p_trunc, p_cntbad; logic [7:0] m_type; logic [1:0] m_err; logic [15:0] m_idx, x_idx, h_count; logic [63:0] h_seq; logic [79:0] h_session;
`include "out/wide_decl.vh"
    mold_wide dut (.clk(clk), .rst(rst), .valid(valid), .sop(sop), .eop(eop), .nb(nb), .data(data), .m_valid(m_valid), .m_type(m_type), .m_err(m_err), .m_idx(m_idx), .h_seq(h_seq), .x_valid(x_valid), .x_idx(x_idx), .p_valid(p_valid), .p_trunc(p_trunc), .p_cntbad(p_cntbad), .h_session(h_session), .h_count(h_count)
`include "out/wide_conn.vh"
    );
    always #4 clk = ~clk;
    always @(posedge clk) if (run) begin
        if (m_valid) begin
`include "out/wide_print.vh"
        end
        if (x_valid) $display("X %0d %0d", cyc, x_idx);
        if (p_valid) $display("P %0d %0d %0d %h %0d", cyc, p_trunc, p_cntbad, h_session, h_count);
        cyc++;
    end
    initial begin
        $readmemh("out/wide_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            {valid, sop, eop} = vec[k][8*WB+7:8*WB+5]; rst = vec[k][8*WB+4]; nb = vec[k][8*WB+3:8*WB]; data = vec[k][8*WB-1:0]; run = 1; @(negedge clk);
        end
        valid = 0; sop = 0; eop = 0; repeat (6) @(negedge clk); $finish;
    end
endmodule
