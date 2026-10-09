// verilator lint_off DECLFILENAME
// Chapter 2: one valid/ready pipeline stage written three ways, and a chain of N stages.
// A transfer happens in a cycle where valid && ready. A stage holds its data while valid && !ready (the stream rule).
// vr_slow:  ready_in = !valid_out. Simple and registered, but a new item can only enter when the stage is empty: half the throughput.
// vr_comb:  ready_in = ready_out || !valid_out. Full throughput, but ready_in depends combinationally on ready_out, so in a chain the ready signal ripples through every stage.
// vr_skid:  a second (skid) register absorbs the item that arrives in the cycle the stall starts, so ready_in can come from a register. Full throughput and no combinational path from output to input.
module vr_slow #(parameter int W = 16) (input logic clk, input logic rst,
    input logic in_valid, output logic in_ready, input logic [W-1:0] in_data,
    output logic out_valid, input logic out_ready, output logic [W-1:0] out_data);
    assign in_ready = !out_valid;
    always_ff @(posedge clk) begin
        if (rst) out_valid <= 1'b0;
        else if (in_valid && in_ready) begin out_valid <= 1'b1; out_data <= in_data; end
        else if (out_ready) out_valid <= 1'b0;
    end
endmodule
module vr_comb #(parameter int W = 16) (input logic clk, input logic rst,
    input logic in_valid, output logic in_ready, input logic [W-1:0] in_data,
    output logic out_valid, input logic out_ready, output logic [W-1:0] out_data);
    assign in_ready = out_ready || !out_valid;
    always_ff @(posedge clk) begin
        if (rst) out_valid <= 1'b0;
        else if (in_ready) begin out_valid <= in_valid; out_data <= in_data; end
    end
endmodule
module vr_skid #(parameter int W = 16) (input logic clk, input logic rst,
    input logic in_valid, output logic in_ready, input logic [W-1:0] in_data,
    output logic out_valid, input logic out_ready, output logic [W-1:0] out_data);
    logic [W-1:0] skid_data; logic skid_valid;
    assign in_ready = !skid_valid;
    always_ff @(posedge clk) begin
        if (rst) begin out_valid <= 1'b0; skid_valid <= 1'b0; end
        else if (out_ready || !out_valid) begin               // the output register is free, or is being emptied now
            if (skid_valid) begin out_data <= skid_data; out_valid <= 1'b1; skid_valid <= 1'b0; end
            else begin out_data <= in_data; out_valid <= in_valid; end
        end else if (in_valid && in_ready) begin              // the output is stalled and an item arrives: park it
            skid_data <= in_data; skid_valid <= 1'b1;
        end
    end
endmodule
// STYLE: 0 slow, 1 comb, 2 skid
module vr_chain #(parameter int W = 16, parameter int N = 4, parameter int STYLE = 2) (input logic clk, input logic rst,
    input logic in_valid, output logic in_ready, input logic [W-1:0] in_data,
    output logic out_valid, input logic out_ready, output logic [W-1:0] out_data);
    logic [N:0] v, r; logic [(N+1)*W-1:0] d;               // the data of all N+1 links, flattened: link k is d[k*W +: W]
    assign v[0] = in_valid; assign d[0 +: W] = in_data; assign in_ready = r[0];
    assign out_valid = v[N]; assign out_data = d[N*W +: W]; assign r[N] = out_ready;
    genvar k;
    generate for (k = 0; k < N; k++) begin : st
        if (STYLE == 0) begin : g_slow
            vr_slow #(W) u (.clk(clk), .rst(rst), .in_valid(v[k]), .in_ready(r[k]), .in_data(d[k*W +: W]), .out_valid(v[k+1]), .out_ready(r[k+1]), .out_data(d[(k+1)*W +: W]));
        end else if (STYLE == 1) begin : g_comb
            vr_comb #(W) u (.clk(clk), .rst(rst), .in_valid(v[k]), .in_ready(r[k]), .in_data(d[k*W +: W]), .out_valid(v[k+1]), .out_ready(r[k+1]), .out_data(d[(k+1)*W +: W]));
        end else begin : g_skid
            vr_skid #(W) u (.clk(clk), .rst(rst), .in_valid(v[k]), .in_ready(r[k]), .in_data(d[k*W +: W]), .out_valid(v[k+1]), .out_ready(r[k+1]), .out_data(d[(k+1)*W +: W]));
        end
    end endgenerate
endmodule
