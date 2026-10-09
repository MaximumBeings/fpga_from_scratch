// Chapter 5: one memory, three ways of reading it. STYLE 0: asynchronous read (the address goes through the array to the output in the same cycle): built from LUTs and flip-flops. STYLE 1: synchronous read (the data appears one cycle after the address): can use a block RAM. STYLE 2: synchronous read with an output register (two cycles): a block RAM and a faster output. A synchronous read of the address being written in the same cycle returns the OLD contents (read-first).
module ram_style #(parameter int W = 16, parameter int D = 256, parameter int STYLE = 1) (
    input logic clk, input logic we, input logic [$clog2(D)-1:0] waddr, input logic [W-1:0] wdata, input logic [$clog2(D)-1:0] raddr, output logic [W-1:0] rdata);
    logic [W-1:0] mem [D]; logic [W-1:0] r1 = '0, r2 = '0;
    initial for (int i = 0; i < D; i++) mem[i] = '0;                  // a block RAM can be loaded with its initial contents at configuration
    always_ff @(posedge clk) begin
        if (we) mem[waddr] <= wdata;
        r1 <= mem[raddr]; r2 <= r1;
    end
    assign rdata = (STYLE == 0) ? mem[raddr] : ((STYLE == 1) ? r1 : r2);
endmodule
