// Chapter 12 testbench for tcp_fast (combinational): replays out/tcp_fast_stim.hex, one line per case: state(1) una nxt rcv seq ack (8 each) flags(1) len(4) wnd(4) hex digits; prints `H <hit> <n_una> <n_rcv> <tx_v> <dlv>` for each case. Define: NC.
`timescale 1ns/1ps
`ifndef NC
`define NC 1000
`endif
module tcp_fast_tb;
    localparam int NC = `NC;
    logic [199:0] vec [0:NC-1]; logic [3:0] st, f; logic [31:0] una, nxt, rcv, seq, ack, n_una, n_rcv; logic [15:0] ln, wnd, dlv; logic hit, tx_v; int k;
    tcp_fast dut (.st(st), .una(una), .nxt(nxt), .rcv(rcv), .f(f), .seq(seq), .ack(ack), .ln(ln), .wnd(wnd), .hit(hit), .n_una(n_una), .n_rcv(n_rcv), .tx_v(tx_v), .dlv(dlv));
    initial begin
        $readmemh("out/tcp_fast_stim.hex", vec);
        for (k = 0; k < NC; k++) begin
            {st, una, nxt, rcv, seq, ack, f, ln, wnd} = vec[k]; #1; $display("H %0d %0d %0d %0d %0d", hit, n_una, n_rcv, tx_v, dlv);
        end
        $display("DONE"); $finish;
    end
endmodule
