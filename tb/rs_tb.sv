// Chapter 5 testbench for fx_round_sat: EVERY input value (exhaustive), compared with out/rs_vec.hex written by model/fx_gold.py. Defines: IW OW SH RND SAT (the same values the model was run with).
`timescale 1ns/1ps
`ifndef IW
`define IW 12
`endif
`ifndef OW
`define OW 6
`endif
`ifndef SH
`define SH 4
`endif
`ifndef RND
`define RND 1
`endif
`ifndef SAT
`define SAT 1
`endif
module rs_tb;
    localparam int IW = `IW, OW = `OW, N = 1 << IW, YH = (OW + 3) / 4;
    logic signed [IW-1:0] x; logic signed [OW-1:0] y; logic [47:0] vec [0:N-1]; int errs = 0, k;
    fx_round_sat #(.IW(IW), .OW(OW), .SH(`SH), .RND(`RND), .SAT(`SAT)) dut (.x(x), .y(y));
    initial begin
        $readmemh("out/rs_vec.hex", vec);
        for (k = 0; k < N; k++) begin
            x = vec[k][YH*4 +: IW]; #1;
            if (y !== vec[k][OW-1:0]) begin errs++; if (errs < 6) $display("MISMATCH x = %0d: got %0d expected %0d", x, y, $signed(vec[k][OW-1:0])); end
        end
        if (errs == 0) $display("PASS: all %0d inputs, IW=%0d OW=%0d SH=%0d RND=%0d SAT=%0d", N, IW, OW, `SH, `RND, `SAT); else $display("FAIL: %0d of %0d inputs wrong", errs, N);
        $finish;
    end
endmodule
