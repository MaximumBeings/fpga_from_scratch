// Chapter 8 testbench for mac_tx_path, optionally looped back into mac_rx_path. Frames (without FCS) come from out/tx_bytes.hex and out/tx_lens.hex; the source offers a frame byte with probability SRC percent per cycle and holds it until s_ready (a compliant AXI-Stream source). Prints `WIRE <hex of every byte sent while tx_en was high> 0` per frame and `GAP <cycles tx_en was low between frames>`; with LOOP = 1 the transmitter output is also fed to mac_rx_path (rx and tx clocks equal, core clock COREP) and the frames it delivers print as `FRAME <hex> 0`. Defines: NF (frames), SRC, LOOP, AW, COREP.
`timescale 1ps/1ps
`ifndef NF
`define NF 10
`endif
`ifndef SRC
`define SRC 100
`endif
`ifndef LOOP
`define LOOP 0
`endif
`ifndef AW
`define AW 11
`endif
`ifndef COREP
`define COREP 6400
`endif
module mac_tx_tb;
    localparam int NF = `NF;
    logic clk = 0, core_clk = 0, rst = 1, s_valid = 0, s_last = 0, s_ready, tx_en, underrun, core_rst_n = 0; logic [7:0] s_data = '0, txd; logic [15:0] n_ok, n_ovf;
    logic [7:0] bytes [0:NF*1600]; logic [15:0] lens [0:NF-1]; int fi = 0, bi = 0, base = 0, k, wn = 0, gapc = 0, nframes = 0, nf_rx = 0; logic [7:0] wbuf [0:2047]; logic started = 0; logic [31:0] rng = 32'h13579bdf;
    mac_tx_path #(.AW(`AW)) dut (.clk(clk), .rst(rst), .s_valid(s_valid), .s_data(s_data), .s_last(s_last), .s_ready(s_ready), .tx_en(tx_en), .txd(txd), .underrun(underrun), .n_ok(n_ok), .n_ovf(n_ovf));
    always #4000 clk = ~clk;
    initial begin #555; forever #(`COREP / 2) core_clk = ~core_clk; end
    always @(posedge clk) begin
        if (tx_en) begin
            if (wn == 0 && started) begin $display("GAP %0d", gapc); end
            wbuf[wn] = txd; wn++; gapc = 0;
        end else begin
            if (wn > 0) begin $write("WIRE "); for (int i = 0; i < wn; i++) $write("%02x", wbuf[i]); $display(" 0"); wn = 0; nframes++; started = 1; end
            gapc++;
        end
    end
    // the source
    always @(posedge clk) if (!rst) begin
        rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5);
        if (!s_valid || s_ready) begin
            if (fi < NF && ((rng % 100) < `SRC)) begin
                s_valid <= 1'b1; s_data <= bytes[base + bi]; s_last <= (bi == lens[fi] - 1);
                if (s_valid && s_ready) ; 
            end
        end
    end
    // advance the source position when a byte was accepted
    always @(posedge clk) if (!rst && s_valid && s_ready) begin
        if (bi == lens[fi] - 1) begin base += lens[fi]; fi++; bi = 0; end else bi++;
        s_valid <= 1'b0;
    end
    logic o_valid, o_last; logic [7:0] o_data; logic [7:0] rbuf [0:2047]; int rn = 0; logic [15:0] rn_ok, rn_bad, rn_ovf, rn_lost;
    if (`LOOP) begin : lp
        mac_rx_path #(.AW(`AW), .CAW(4)) rxp (.rx_clk(clk), .rx_rst_n(!rst), .rx_dv(tx_en), .rx_er(1'b0), .rxd(txd), .core_clk(core_clk), .core_rst_n(core_rst_n),
            .o_valid(o_valid), .o_data(o_data), .o_last(o_last), .o_ready(1'b1), .n_ok(rn_ok), .n_bad(rn_bad), .n_ovf(rn_ovf), .n_lost(rn_lost));
        always @(posedge core_clk) if (o_valid) begin rbuf[rn] = o_data; rn++; if (o_last) begin $write("FRAME "); for (int i = 0; i < rn; i++) $write("%02x", rbuf[i]); $display(" 0"); rn = 0; nf_rx++; end end
    end
    initial begin
        $readmemh("out/tx_bytes.hex", bytes); $readmemh("out/tx_lens.hex", lens);
        repeat (4) @(negedge clk); rst = 0; repeat (4) @(negedge core_clk); core_rst_n = 1;
        wait (fi == NF); repeat (30000) @(negedge clk);
        $display("STATS %0d %0d %0d", n_ok, n_ovf, underrun); $display("DONE %0d wire frames", nframes); $finish;
    end
endmodule
