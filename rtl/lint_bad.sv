// verilator lint_off DECLFILENAME
// Chapter 2: a module with five classic mistakes, each of which compiles and may even simulate. A lint tool finds them without running anything.
module lint_bad (input logic clk, input logic [7:0] a, input logic [3:0] b, input logic [1:0] sel, input logic en, output logic [3:0] y, output logic [7:0] q, output logic z);
    logic [3:0] narrow;
    always_comb narrow = a;                                   // 1. WIDTHTRUNC: 8 bits assigned to 4: the top four bits are silently lost
    always_comb if (en) y = narrow ^ b;                       // 2. LATCH: y is not assigned when en = 0, so a latch is built
    always_comb case (sel) 2'd0: z = a[0]; 2'd1: z = a[1]; endcase   // 3. CASEINCOMPLETE (and a latch): sel = 2 or 3 leave z unassigned
    always_ff @(posedge clk) begin q = a; end                 // 4. BLKSEQ: a blocking assignment in a clocked block
    assign z = en;                                            // 5. MULTIDRIVEN: z is also driven by the case above
endmodule
