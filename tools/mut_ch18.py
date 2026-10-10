#!/usr/bin/env python3
"""Chapter 18: test the tests. Two families. (1) mutants of rtl/seq_arb.sv, battery `ch18_run.py --battery`: seq_arb against the cycle model, every output and the state after every cycle, four configurations, closed-loop runs and random inputs. (2) mutants of model/arb_gold.py, battery `--battery-model`: the model's hand-checked scenarios and the end-to-end property (the messages forwarded tile the sequence space)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/seq_arb.sv"; MOD = "model/arb_gold.py"
MUT = [
 (RTL, "the minimum is the largest distance", "if (mv[i + sdp] < mv[i]) mv[i] = mv[i + sdp];", "if (mv[i + sdp] > mv[i]) mv[i] = mv[i + sdp];"),
 (RTL, "a stored packet is in order one early", "if (di == 32'd0) begin rel_any", "if (di == 32'd1) begin rel_any"),
 (RTL, "a gap is any stored packet", "gap = has_pend && !rel_any;", "gap = has_pend;"),
 (RTL, "the request is one cycle late", "(tmr == 16'(TO));", "(tmr == 16'(TO + 1));"),
 (RTL, "the skip does not wait for a request", "skip_fire = gap && req && (tmr == 16'(TO2));", "skip_fire = gap && (tmr == 16'(TO2));"),
 (RTL, "the skip is one cycle early", "(tmr == 16'(TO2));", "(tmr == 16'(TO2 - 1));"),
 (RTL, "the input is accepted during a skip", "in_ready = !rel_any && !skip_fire;", "in_ready = !rel_any;"),
 (RTL, "the input is accepted during a release", "in_ready = !rel_any && !skip_fire;", "in_ready = !skip_fire;"),
 (RTL, "the input is always accepted", "in_ready = !rel_any && !skip_fire;", "in_ready = 1'b1;"),
 (RTL, "the request count is not capped", "t_cnt <= (mind > 32'hffff) ? 32'hffff : mind;", "t_cnt <= mind;"),
 (RTL, "the request is for the minimum, not for the next", "t_kind <= 2'd1; t_seq <= nx;", "t_kind <= 2'd1; t_seq <= nx + mind;"),
 (RTL, "the skip reports a count of 1", "t_kind <= 2'd2; t_seq <= nx; t_cnt <= mind;", "t_kind <= 2'd2; t_seq <= nx; t_cnt <= 32'd1;"),
 (RTL, "a copy of a stored packet is not recognised", "if (sd[i] == d) same = 1'b1;", ""),
 (RTL, "a stored packet is compared by its distance with the wrong value", "if (sd[i] == d) same = 1'b1;", "if (sd[i] == in_seq) same = 1'b1;"),
 (RTL, "the skip does not move the expected number", "skip_fire ? mind :", "skip_fire ? 32'd0 :"),
 (RTL, "a release advances by one", "rel_any ? {16'd0, sc[rel_idx]} :", "rel_any ? 32'd1 :"),
 (RTL, "a forward does not advance the expected number", "? {16'd0, in_cnt} : 32'd0;", "? 32'd0 : 32'd0;"),
 (RTL, "a forward advances by one", "? {16'd0, in_cnt} : 32'd0;", "? 32'd1 : 32'd0;"),
 (RTL, "the distances are not reduced when the expected number advances", "sd[i] <= sd[i] - delta;", "sd[i] <= sd[i];"),
 (RTL, "the stored distance is the sequence number", "sd[free_idx] <= d;", "sd[free_idx] <= in_seq;"),
 (RTL, "a release reports no sequence number", "d_kind <= 3'd6; d_seq <= nx;", "d_kind <= 3'd6; d_seq <= 32'd0;"),
 (RTL, "a release does not free the slot", "sv[rel_idx] <= 1'b0;", ""),
 (RTL, "an empty slot takes part in the minimum", "(sv[i % PEND] ? sd[i % PEND] : 32'hffffffff)", "sd[i % PEND]"),
 (RTL, "the padding of the tree is zero", ": 32'hffffffff;\n        for (int sdp", ": 32'h0;\n        for (int sdp"),
 (RTL, "a release is reported as a forward", "d_kind <= 3'd6;", "d_kind <= 3'd0;"),
 (RTL, "a release reports the feed of the input", "d_feed <= sf[rel_idx];", "d_feed <= in_feed;"),
 (RTL, "a release reports the count of the input", "d_cnt <= sc[rel_idx];", "d_cnt <= in_cnt;"),
 (RTL, "a heartbeat is not recognised", "if (cnt0) d_kind <= 3'd5;", "if (1'b0) d_kind <= 3'd5;"),
 (RTL, "a packet that overlaps the expected number is a duplicate", "d_kind <= dup_beh ? 3'd2 : 3'd3;", "d_kind <= 3'd2;"),
 (RTL, "a packet ending exactly at the expected number is not a duplicate", "dup_beh = e[31] || (e == 32'd0);", "dup_beh = e[31];"),
 (RTL, "a packet behind the expected number is tested by the wrong bit", "bh = d[31];", "bh = d[30];"),
 (RTL, "a copy of a stored packet is stored again", "else if (same) d_kind <= 3'd2;", "else if (1'b0) d_kind <= 3'd2;"),
 (RTL, "a full table drops silently as a store", "else d_kind <= 3'd4;", "else d_kind <= 3'd1;"),
 (RTL, "the stored packet loses its feed", "sf[free_idx] <= in_feed;", "sf[free_idx] <= 2'd0;"),
 (RTL, "the stored packet loses its count", "sc[free_idx] <= in_cnt;", "sc[free_idx] <= 16'd1;"),
 (RTL, "outside a gap the timer is not cleared", "if (!gap) begin tmr <= 16'd0; req <= 1'b0; end", "if (!gap) begin req <= 1'b0; end"),
 (RTL, "outside a gap the request flag is not cleared", "if (!gap) begin tmr <= 16'd0; req <= 1'b0; end", "if (!gap) begin tmr <= 16'd0; end"),
 (RTL, "a request does not set the flag", "else if (req_fire) begin tmr <= 16'd0; req <= 1'b1; end", "else if (req_fire) begin tmr <= 16'd0; end"),
 (RTL, "the timer counts by two", "else tmr <= tmr + 16'd1;", "else tmr <= tmr + 16'd2;"),
 (RTL, "the expected number starts at 1", "nx <= INIT;", "nx <= 32'd1;"),
 (RTL, "reset does not clear the slots", "for (int i = 0; i < PEND; i++) sv[i] <= 1'b0;", ""),
 (RTL, "the slot count is wrong", "np = np + 4'd1;", "np = np + 4'd2;"),
 (MOD, "model: the request count is not capped", "self.next, min(mind, 0xFFFF), (0, 1)", "self.next, mind, (0, 1)"),
 (MOD, "model: the skip does not move the expected number", "elif tk == SKIP: self.next = (self.next + tc) & M", "elif tk == SKIP: pass"),
 (MOD, "model: a packet behind next is always a duplicate", "(DUP if (behind(e) or e == 0) else BAD, q, c, f)", "(DUP, q, c, f)"),
 (MOD, "model: a copy of a stored packet is stored again", "elif any(s and s[0] == q for s in self.slots): dec = (DUP, q, c, f)", "elif False: dec = (DUP, q, c, f)"),
 (MOD, "model: heartbeats are forwarded", "if c == 0: dec = (HB, q, c, f)", "if False: dec = (HB, q, c, f)"),
 (MOD, "model: a release advances by one", "self.next = (self.next + s[1]) & M", "self.next = (self.next + 1) & M"),
 (MOD, "model: the input is accepted during a release", "return self._rel() is None and self._timer()[0] != SKIP", "return self._timer()[0] != SKIP"),
 (MOD, "model: a full table stores anyway", "else: dec = (OVF, q, c, f)", "else: self.slots[0] = (q, c, f); dec = (STORE, q, c, f)"),
 (MOD, "model: the request does not wait for TO", "if not self.req and self.tmr == self.to:", "if not self.req and self.tmr == self.to - 1:"),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut18_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex17_*", "t17_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch18_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch18_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch18_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
