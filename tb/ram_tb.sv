// Chapter 5 testbench for ram_style: random writes and reads (a fifth of the reads hit the address being written) against the golden model, every cycle. Defines: D (depth), STYLE, NC. Width is 16.
`timescale 1ns/1ps
`ifndef D
`define D 256
`endif
`ifndef STYLE
`define STYLE 1
`endif
`ifndef NC
`define NC 3000
`endif
module ram_tb;
    localparam int D = `D, NC = `NC, AW = $clog2(D);
    logic clk = 0, we = 0; logic [AW-1:0] waddr = '0, raddr = '0; logic [15:0] wdata = '0, rdata; logic [71:0] vec [0:NC-1]; int errs = 0, k;
    ram_style #(.W(16), .D(D), .STYLE(`STYLE)) dut (.clk(clk), .we(we), .waddr(waddr), .wdata(wdata), .raddr(raddr), .rdata(rdata));
    always #5 clk = ~clk;
    initial begin
        $readmemh("out/ram_vec.hex", vec);
        for (k = 0; k < NC; k++) begin
            @(negedge clk); we = vec[k][64]; waddr = vec[k][48 +: AW]; wdata = vec[k][47:32]; raddr = vec[k][16 +: AW]; #1;
            if (rdata !== vec[k][15:0]) begin errs++; if (errs < 6) $display("MISMATCH cycle %0d: rdata %h expected %h", k, rdata, vec[k][15:0]); end
        end
        if (errs == 0) $display("PASS: depth %0d, style %0d, %0d cycles", D, `STYLE, NC); else $display("FAIL: %0d problems", errs);
        $finish;
    end
endmodule
