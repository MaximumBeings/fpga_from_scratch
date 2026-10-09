#!/usr/bin/env python3
"""Chapter 2: test the tests of the running designs. Each mutant breaks one line of rtl/vr.sv (testbench: golden vectors in a mix of five traffic profiles, the protocol test and the throughput run, 4-stage chains) or of rtl/frame_fsm.sv (testbench: 3,000 golden cycles, all three recognizers). Equivalent changes are listed apart."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, vr_gold, frame_gold
V = "rtl/vr.sv"; Fm = "rtl/frame_fsm.sv"
SLOW = [
 (V, "slow: ready is the inverse of the usual (ready = valid)", "assign in_ready = !out_valid;\n    always_ff @(posedge clk) begin\n        if (rst) out_valid <= 1'b0;\n        else if (in_valid && in_ready) begin out_valid <= 1'b1; out_data <= in_data; end", "assign in_ready = out_valid;\n    always_ff @(posedge clk) begin\n        if (rst) out_valid <= 1'b0;\n        else if (in_valid && in_ready) begin out_valid <= 1'b1; out_data <= in_data; end"),
 (V, "slow: the item is never freed when the sink takes it", "else if (out_ready) out_valid <= 1'b0;\n    end\nendmodule\nmodule vr_comb", "else if (out_ready && 1'b0) out_valid <= 1'b0;\n    end\nendmodule\nmodule vr_comb"),
 (V, "slow: the data register captures zero", "begin out_valid <= 1'b1; out_data <= in_data; end\n        else if (out_ready)", "begin out_valid <= 1'b1; out_data <= '0; end\n        else if (out_ready)"),
 (V, "slow: reset does not clear valid", "if (rst) out_valid <= 1'b0;\n        else if (in_valid && in_ready) begin out_valid <= 1'b1;", "if (rst) out_valid <= out_valid;\n        else if (in_valid && in_ready) begin out_valid <= 1'b1;"),
]
COMB = [
 (V, "comb: ready follows the sink only", "assign in_ready = out_ready || !out_valid;", "assign in_ready = out_ready;"),
 (V, "comb: ready is high when the stage is full and the sink is not ready... or valid", "assign in_ready = out_ready || !out_valid;", "assign in_ready = out_ready || out_valid;"),
 (V, "comb: valid is always set after an accepted cycle", "else if (in_ready) begin out_valid <= in_valid; out_data <= in_data; end\n    end\nendmodule\nmodule vr_skid", "else if (in_ready) begin out_valid <= 1'b1; out_data <= in_data; end\n    end\nendmodule\nmodule vr_skid"),
 (V, "comb: the stage loads new data even when it is not ready", "else if (in_ready) begin out_valid <= in_valid; out_data <= in_data; end\n    end\nendmodule\nmodule vr_skid", "else begin out_valid <= in_valid; out_data <= in_data; end\n    end\nendmodule\nmodule vr_skid"),
]
SKID = [
 (V, "skid: ready is always high", "assign in_ready = !skid_valid;", "assign in_ready = 1'b1;"),
 (V, "skid: the parked item is never marked valid", "skid_data <= in_data; skid_valid <= 1'b1;", "skid_data <= in_data; skid_valid <= 1'b0;"),
 (V, "skid: the parked item is released from the input instead of the skid register", "if (skid_valid) begin out_data <= skid_data;", "if (skid_valid) begin out_data <= in_data;"),
 (V, "skid: the output register only loads when the sink is ready (not when it is empty)", "else if (out_ready || !out_valid) begin               // the output register is free, or is being emptied now", "else if (out_ready) begin               // the output register is free, or is being emptied now"),
 (V, "skid: an arriving item is marked valid even when the input is idle", "else begin out_data <= in_data; out_valid <= in_valid; end", "else begin out_data <= in_data; out_valid <= 1'b1; end"),
 (V, "skid: a second item overwrites the parked one", "end else if (in_valid && in_ready) begin              // the output is stalled and an item arrives: park it", "end else if (in_valid) begin              // the output is stalled and an item arrives: park it"),
]
FSM = [
 (Fm, "frame_a: the start byte is 0xA4", "2'd0: if (in_byte == 8'hA5) st <= 2'd1;", "2'd0: if (in_byte == 8'hA4) st <= 2'd1;"),
 (Fm, "frame_a: a length of 17 is accepted", "2'd1: if (in_byte >= 8'd1 && in_byte <= 8'd16) begin cnt", "2'd1: if (in_byte >= 8'd1 && in_byte <= 8'd17) begin cnt"),
 (Fm, "frame_a: payload bytes are not reported", "2'd2: begin pay_v <= 1'b1; cnt <= cnt - 5'd1;", "2'd2: begin pay_v <= 1'b0; cnt <= cnt - 5'd1;"),
 (Fm, "frame_a: the end byte is 0x5B", "default: begin if (in_byte == 8'h5A) done <= 1'b1; else err <= 1'b1; st <= 2'd0; end", "default: begin if (in_byte == 8'h5B) done <= 1'b1; else err <= 1'b1; st <= 2'd0; end"),
 (Fm, "frame_a: idle cycles (valid low) are treated as data", "else if (in_valid) begin\n            case (st)\n                2'd0:", "else begin\n            case (st)\n                2'd0:"),
 (Fm, "frame_a: busy is high only in the data state", "assign busy = (st != 2'd0);", "assign busy = (st == 2'd2);"),
 (Fm, "frame_b: the start byte is 0xA4", "IDLE: if (in_byte == 8'hA5) nx = LEN;", "IDLE: if (in_byte == 8'hA4) nx = LEN;"),
 (Fm, "frame_b: the count ends one byte early", "if (cnt == 5'd1) nx = FIN; end", "if (cnt == 5'd2) nx = FIN; end"),
 (Fm, "frame_b: a bad end byte is not reported", "FIN: begin if (in_byte == 8'h5A) done_n = 1'b1; else err_n = 1'b1; nx = IDLE; end", "FIN: begin if (in_byte == 8'h5A) done_n = 1'b1; else err_n = 1'b0; nx = IDLE; end"),
 (Fm, "frame_b: reset enters the LEN state", "if (rst) begin st <= IDLE; cnt <= 5'd0;", "if (rst) begin st <= LEN; cnt <= 5'd0;"),
 (Fm, "frame_b: a zero length is accepted", "LEN: if (in_byte >= 8'd1 && in_byte <= 8'd16) begin cnt_n", "LEN: if (in_byte >= 8'd0 && in_byte <= 8'd16) begin cnt_n"),
 (Fm, "frame_c: the one-hot machine never returns to idle after a frame", "|| (s_len && !good_len) || s_fin;", "|| (s_len && !good_len);"),
 (Fm, "frame_c: the count ends one byte late", "s_data <= (s_len && good_len) || (s_data && cnt != 5'd1);", "s_data <= (s_len && good_len) || (s_data && cnt != 5'd0);"),
 (Fm, "frame_c: a length of 15 or less only", "assign good_len = (in_byte >= 8'd1) && (in_byte <= 8'd16);", "assign good_len = (in_byte >= 8'd1) && (in_byte <= 8'd15);"),
 (Fm, "frame_c: a bad length is not reported", "if (s_len && !good_len) err <= 1'b1;", "if (s_len && !good_len) err <= 1'b0;"),
 (Fm, "frame_c: busy is high only in the data state", "assign busy = !s_idle;", "assign busy = s_data;"),
]
EQUIV = [(Fm, "EQUIVALENT: frame_a's counter is reset to 7 instead of 0 (it is loaded from the length byte before it is ever used, and is not an output)", "if (rst) begin st <= 2'd0; cnt <= 5'd0; end\n        else if (in_valid) begin", "if (rst) begin st <= 2'd0; cnt <= 5'd7; end\n        else if (in_valid) begin")]
R = flow.ROOT; tot = 0; caught = 0; lines = []
for st, group in enumerate((SLOW, COMB, SKID)):
    vr_gold.write(st, 4, 16, 500, 1, "mixed", os.path.join(R, "out", "vr_vec.hex")); d = ("WIDTH=16", "NSTAGES=4", f"STYLE={st}", "NCYC=500")
    c, n, l = flow.mutate(group, [V], "vr_tb", ["tb/vr_tb.sv"], workers=4, defines=d); caught += c; tot += n; lines += l
frame_gold.write(3000, 1, os.path.join(R, "out", "frame_vec.hex"))
c, n, l = flow.mutate(FSM, [Fm], "frame_tb", ["tb/frame_tb.sv"], workers=4, defines=("NCYC=3000",)); caught += c; tot += n; lines += l
print("NOTE: this script deliberately breaks copies of the RTL. 'caught' lines are EXPECTED: they show the testbench notices the mistake.")
print("\n".join(lines)); print(f"\nvalid/ready stages and frame recognizers: {caught} of {tot} broken circuits caught")
c2, n2, l2 = flow.mutate(EQUIV, [Fm], "frame_tb", ["tb/frame_tb.sv"], workers=1, defines=("NCYC=3000",)); print("\nChanges that look like bugs and are not:"); print("\n".join(l2))
sys.exit(0 if caught == tot else 1)
