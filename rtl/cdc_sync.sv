// verilator lint_off DECLFILENAME
// Chapter 3: the two-flip-flop synchronizer. A signal from another clock domain can change at any moment relative to this domain's clock edge; if it changes too close to the edge the first flip-flop may go METASTABLE (neither 0 nor 1 for a while). The second flip-flop gives it a whole clock period to settle before anything uses it.
// Rules for use: (1) ONE bit, or a bus whose bits can be safely captured at different times (a Gray-coded counter: only one bit changes per step); (2) the source must be a flip-flop output, with no logic between it and this synchronizer; (3) the first flip-flop's output feeds ONLY the second.
// The attribute tells vendor tools to place the two flip-flops together and not to optimize them. (This module is replaced in one testbench by a model with random metastability resolution: tb/cdc_sync_meta.sv has the same name and ports.)
module cdc_sync #(parameter int W = 1) (input logic clk, input logic [W-1:0] d, output logic [W-1:0] q);
    (* async_reg = "true" *) logic [W-1:0] m = '0;                  // initial values: the FPGA loads them at configuration, so a synchronizer never starts with an unknown
    logic [W-1:0] q_r = '0;
    always_ff @(posedge clk) begin m <= d; q_r <= m; end
    assign q = q_r;
endmodule
