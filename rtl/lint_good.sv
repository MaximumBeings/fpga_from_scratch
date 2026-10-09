// verilator lint_off DECLFILENAME
// Chapter 2: the same interface with the mistakes repaired; the lint tool has nothing to say.
module lint_good (input logic clk, input logic [7:0] a, input logic [3:0] b, input logic [1:0] sel, input logic en, output logic [3:0] y, output logic [7:0] q, output logic z);
    logic [3:0] narrow;
    always_comb narrow = a[3:0];                              // the narrowing is now explicit
    always_comb begin y = 4'd0; if (en) y = narrow ^ b; end   // a default for every path: no latch
    always_comb begin
        z = 1'b0;
        case (sel) 2'd0: z = a[0]; 2'd1: z = a[1]; 2'd2: z = en; default: z = 1'b0; endcase   // every case covered, one driver
    end
    always_ff @(posedge clk) q <= a;                          // non-blocking in a clocked block
endmodule
