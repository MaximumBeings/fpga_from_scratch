// Chapter 6: formal properties of sfifo, for Yosys's SAT engine. The wrapper instantiates the design, drives it with free (unconstrained) inputs, and asserts what the specification says. Yosys treats every undriven input as "any value, any cycle".
// Properties: (1) count never exceeds DEPTH, (2) full and empty agree with count, (3) a model of the occupancy kept in the wrapper agrees with count (so a write/read that changes the count the wrong way is caught), (4) a tagged word: pick any word (an $anyconst index K) and assert that the K-th word read is the K-th word written.
module sfifo_props #(parameter int BUG = 0, parameter int DEPTH = 6) (input logic clk, input logic wr_en, input logic [7:0] wr_data, input logic rd_en);
    logic rst; logic [7:0] rd_data; logic full, empty; logic [2:0] count;
    sfifo #(.W(8), .DEPTH(DEPTH), .BUG(BUG)) dut (.clk(clk), .rst(rst), .wr_en(wr_en), .wr_data(wr_data), .rd_en(rd_en), .rd_data(rd_data), .full(full), .empty(empty), .count(count));
    logic started = 1'b0; logic [2:0] occ = 3'd0;                     // the wrapper's own occupancy model
    logic [3:0] nw = 4'd0, nr = 4'd0; (* anyconst *) logic [3:0] k; logic [7:0] tag = 8'd0; logic tagged = 1'b0;
    initial rst = 1'b1;
    always @(posedge clk) begin
        rst <= 1'b0; started <= 1'b1;
        if (!rst) begin
            if (wr_en && occ != DEPTH[2:0]) begin occ <= occ + 1'b1 - ((rd_en && occ != 0) ? 1'b1 : 1'b0); nw <= nw + 1'b1; if (nw == k) begin tag <= wr_data; tagged <= 1'b1; end end
            else if (rd_en && occ != 0) occ <= occ - 1'b1;
            if (rd_en && occ != 0) nr <= nr + 1'b1;
        end
    end
    always @(*) if (started && !rst) begin
        assert (count <= DEPTH[2:0]);
        assert (full == (count == DEPTH[2:0]));
        assert (empty == (count == 3'd0));
        assert (count == occ);
        if (!empty && nr == k && tagged) assert (rd_data == tag);
    end
endmodule
