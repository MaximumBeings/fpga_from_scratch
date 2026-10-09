// verilator lint_off DECLFILENAME
// Chapter 3 simulation model of a synchronizer WITH metastability: same name and ports as rtl/cdc_sync.sv, so a testbench compiled with THIS file instead of the real one sees a synchronizer whose first flip-flop resolves randomly when its input changes close to the clock edge.
// Model: if a bit of d changed less than WINDOW picoseconds before the capturing edge, the first flip-flop captures either its OLD or its NEW value, at random (a xorshift generator keeps runs identical in every simulator). Real metastability can also take longer to resolve; this model covers the case that matters for a bus: each bit independently picks old or new.
`timescale 1ps/1ps
module cdc_sync #(parameter int W = 1) (input logic clk, input logic [W-1:0] d, output logic [W-1:0] q);
    localparam longint WINDOW = 1800;
    logic [W-1:0] m = '0, q_r = '0, dold, dprev; longint tchg [W]; logic [31:0] rng = 32'h9e3779b9;
    initial begin dprev = d; dold = d; for (int i = 0; i < W; i++) tchg[i] = -100000; end
    always @(d) begin
        for (int i = 0; i < W; i++) if (d[i] !== dprev[i]) begin dold[i] = dprev[i]; tchg[i] = $time; end
        dprev = d;
    end
    always @(posedge clk) begin
        for (int i = 0; i < W; i++) begin
            rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5);
            if (($time - tchg[i]) < WINDOW && rng[7]) begin m[i] <= dold[i]; end else m[i] <= d[i];
        end
        q_r <= m;
    end
    assign q = q_r;
endmodule
