// Chapter 3 testbench for the two pulse crossings. Defines: AP, BP (clock periods in ps), OFF (b clock phase in ps), GAP (a-clock cycles between pulses), NP (pulses), TOGGLE (1 = cdc_toggle_pulse, 0 = cdc_naive_pulse).
// The a side raises a_pulse for exactly one a-clock cycle, NP times, GAP cycles apart; the testbench counts the pulses that come out on the b side (one count per b-clock cycle in which b_pulse is high) and prints the count. tools/cdc_model.py predicts the same count from the clock edges alone.
`timescale 1ps/1ps
`ifndef TOGGLE
`define TOGGLE 1
`endif
`ifndef AP
`define AP 10000
`endif
`ifndef BP
`define BP 7300
`endif
`ifndef OFF
`define OFF 1234
`endif
`ifndef GAP
`define GAP 6
`endif
`ifndef NP
`define NP 200
`endif
module cdc_pulse_tb;
    logic aclk = 0, bclk = 0, a_pulse = 0, b_pulse; int got = 0, sent = 0;
    if (`TOGGLE) begin : g1 cdc_toggle_pulse dut (.aclk(aclk), .bclk(bclk), .a_pulse(a_pulse), .b_pulse(b_pulse)); end
    else begin : g0 cdc_naive_pulse dut (.aclk(aclk), .bclk(bclk), .a_pulse(a_pulse), .b_pulse(b_pulse)); end
    always #(`AP / 2) aclk = ~aclk;
    initial begin #(`OFF); forever #(`BP / 2) bclk = ~bclk; end
    always @(posedge bclk) if (b_pulse === 1'b1) got++;
    initial begin
        repeat (4) @(posedge aclk);
        repeat (`NP) begin
            #200 a_pulse = 1; sent++; @(posedge aclk); #200 a_pulse = 0;
            repeat (`GAP - 1) @(posedge aclk);
        end
        repeat (10) @(posedge aclk); repeat (10) @(posedge bclk);              // drain: the slowest crossing takes four b edges
        $display("PULSES sent %0d got %0d", sent, got); $finish;
    end
endmodule
