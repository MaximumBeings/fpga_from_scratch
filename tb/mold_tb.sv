// Chapter 16 testbench for the generated parser mold_itch (rtl/mold_itch.sv): line k of out/mold_stim.hex is presented in cycle k: valid(bit 11) sop(10) eop(9) rst(8) data(7:0); a line with valid = 0 carries random junk in the other signals. Before every clock edge it prints the outputs that are valid:
//   M <cycle> <type> <err> <idx> <seq> <fields as hex, in the order of tools/gen_parser.py's port list>      (one per message)
//   P <cycle> <trunc> <cntbad> <session> <count>                                                          (one per packet end)
// <cycle> is the cycle number of the clock edge at which the line is seen (the line of the last byte is cycle c, its message appears at cycle c + 1). The declarations, port connections and print statement of the fields are the include files out/mold_decl.vh, mold_conn.vh and mold_print.vh, written by tools/gen_parser.py for the grammar.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
module mold_tb;
    localparam int NC = `NC;
    logic clk = 0, rst = 1, valid = 0, sop = 0, eop = 0; logic [7:0] data = '0; logic [11:0] vec [0:NC-1]; int k, cyc = 0; logic run = 0;
    logic m_valid, p_valid, p_trunc, p_cntbad; logic [7:0] m_type; logic [1:0] m_err; logic [15:0] m_idx, h_count; logic [63:0] h_seq; logic [79:0] h_session;
`include "out/mold_decl.vh"
    mold_itch dut (.clk(clk), .rst(rst), .valid(valid), .sop(sop), .eop(eop), .data(data), .m_valid(m_valid), .m_type(m_type), .m_err(m_err), .m_idx(m_idx), .h_seq(h_seq), .p_valid(p_valid), .p_trunc(p_trunc), .p_cntbad(p_cntbad), .h_session(h_session), .h_count(h_count)
`include "out/mold_conn.vh"
    );
    always #4 clk = ~clk;
    always @(posedge clk) if (run) begin
        if (m_valid) begin
`include "out/mold_print.vh"
        end
        if (p_valid) $display("P %0d %0d %0d %h %0d", cyc, p_trunc, p_cntbad, h_session, h_count);
        cyc++;
    end
    initial begin
        $readmemh("out/mold_stim.hex", vec);
        repeat (3) @(negedge clk); rst = 0;
        for (k = 0; k < NC; k++) begin
            {valid, sop, eop} = vec[k][11:9]; rst = vec[k][8]; data = vec[k][7:0]; run = 1; @(negedge clk);
        end
        valid = 0; sop = 0; eop = 0; repeat (6) @(negedge clk); $finish;
    end
endmodule
