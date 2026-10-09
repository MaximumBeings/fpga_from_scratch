#!/usr/bin/env python3
"""Chapter 15: test the tests. Two families. (1) mutants of rtl/split.sv, battery: tcp_split against the cycle model, every output after every edge, on five configurations (FIFO depth 2, 3, 4 and 8; both policies; software latency 1 to 24; 4 and 8 connections) over three kinds of stream (realistic traffic, random events, the directed lives; application commands carry decoy segment fields). (2) mutants of model/split_gold.py, battery: split_gold.battery(), i.e. TRANSPARENCY (the split equals the single state machine) over streams, timings, depths and both policies."""
import concurrent.futures as cf, os, random, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import flow, hw
RTL = "rtl/split.sv"; MOD = "model/split_gold.py"
MUT = [
 (RTL, "the event type is not looked at", "hot = ev_valid && (ev_type == 3'd5) && (cnt == 4'd0) && hit_raw;", "hot = ev_valid && (cnt == 4'd0) && hit_raw;"),
 (RTL, "pending events do not stop the hot path", "hot = ev_valid && (ev_type == 3'd5) && (cnt == 4'd0) && hit_raw;", "hot = ev_valid && (ev_type == 3'd5) && hit_raw;"),
 (RTL, "the hot path is never taken", "hot = ev_valid && (ev_type == 3'd5) && (cnt == 4'd0) && hit_raw;", "hot = 1'b0;"),
 (RTL, "the hot decision ignores tcp_fast", "hot = ev_valid && (ev_type == 3'd5) && (cnt == 4'd0) && hit_raw;", "hot = ev_valid && (ev_type == 3'd5) && (cnt == 4'd0);"),
 (RTL, "pending is a single flag, not a count", "t_cnt[ev_cid] <= cnt + 4'd1;", "t_cnt[ev_cid] <= 4'd1;"),
 (RTL, "POLICY 0 also holds hot events when the FIFO is full", "ev_ready = (POLICY == 0) ? !(punt && full) : 1'b1;", "ev_ready = (POLICY == 0) ? !full : 1'b1;"),
 (RTL, "POLICY 0 never holds", "ev_ready = (POLICY == 0) ? !(punt && full) : 1'b1;", "ev_ready = 1'b1;"),
 (RTL, "POLICY 1 holds", "ev_ready = (POLICY == 0) ? !(punt && full) : 1'b1;", "ev_ready = !(punt && full);"),
 (RTL, "the FIFO is declared full one entry early", "full = (count == CNTW'(DEPTH));", "full = (count >= CNTW'(DEPTH - 1));"),
 (RTL, "an event is pushed even when the FIFO is full", "pushed = consumed && punt && !full;", "pushed = consumed && punt;"),
 (RTL, "a dropped event is not counted as dropped", "drop = consumed && punt && full;", "drop = 1'b0;"),
 (RTL, "an event is consumed without ev_valid", "consumed = ev_valid && ev_ready;", "consumed = ev_ready;"),
 (RTL, "the entry's first flag is always 1", "(cnt == 4'd0)};", "1'b1};"),
 (RTL, "the entry's first flag is always 0", "(cnt == 4'd0)};", "1'b0};"),
 (RTL, "the snapshot's SND.NXT is SND.UNA", "ev_iss, st, pas, una, nxt, rcv,", "ev_iss, st, pas, una, una, rcv,"),
 (RTL, "the snapshot's RCV.NXT is SND.NXT", "ev_iss, st, pas, una, nxt, rcv,", "ev_iss, st, pas, una, nxt, nxt,"),
 (RTL, "the snapshot lacks the passive flag", "ev_iss, st, pas, una, nxt, rcv,", "ev_iss, st, 1'b0, una, nxt, rcv,"),
 (RTL, "the snapshot's state is CLOSED", "ev_iss, st, pas, una, nxt, rcv,", "ev_iss, 4'd0, pas, una, nxt, rcv,"),
 (RTL, "the entry lacks the initial sequence number", "ev_wnd, ev_iss, st,", "ev_wnd, 32'd0, st,"),
 (RTL, "the entry lacks the window", "ev_ln, ev_wnd, ev_iss,", "ev_ln, 16'd0, ev_iss,"),
 (RTL, "the entry lacks the connection number", "entry = {ev_cid, ev_type,", "entry = {{CIDW{1'b0}}, ev_type,"),
 (RTL, "the result path codes hot and punted the same", "r_path <= hot ? 2'd0 : (drop ? 2'd2 : 2'd1);", "r_path <= hot ? 2'd1 : (drop ? 2'd2 : 2'd1);"),
 (RTL, "a dropped event is reported as punted", "r_path <= hot ? 2'd0 : (drop ? 2'd2 : 2'd1);", "r_path <= hot ? 2'd0 : 2'd1;"),
 (RTL, "the hot path does not update RCV.NXT", "if (hot) t_rcv[ev_cid] <= n_rcv_f;", "if (hot) t_rcv[ev_cid] <= rcv;"),
 (RTL, "the hot ACK acknowledges the old RCV.NXT", "r_txack <= tx_v_i ? n_rcv_f : 32'd0;", "r_txack <= tx_v_i ? rcv : 32'd0;"),
 (RTL, "the hot ACK has the wrong flags", "r_txf <= tx_v_i ? 4'd2 : 4'd0;", "r_txf <= tx_v_i ? 4'd3 : 4'd0;"),
 (RTL, "a pure ACK produces a segment", "r_txv <= tx_v_i;", "r_txv <= 1'b1;"),
 (RTL, "the delivered count is not reported", "r_dlv <= dlv_f; end", "end"),
 (RTL, "the write-back does not write SND.UNA", "t_una[wb_cid] <= wb_una; t_nxt", "t_nxt"),
 (RTL, "the write-back does not write SND.NXT", "t_nxt[wb_cid] <= wb_nxt; t_rcv", "t_rcv"),
 (RTL, "the write-back does not write RCV.NXT", "t_rcv[wb_cid] <= wb_rcv;\n", "\n"),
 (RTL, "the write-back does not write the state", "t_st[wb_cid] <= wb_st; t_pas", "t_pas"),
 (RTL, "the write-back does not write the passive flag", "t_pas[wb_cid] <= wb_pas; t_una", "t_una"),
 (RTL, "the write-back does not decrement the count", "t_cnt[wb_cid] <= t_cnt[wb_cid] - 4'd1 + ((pushed && ev_cid == wb_cid) ? 4'd1 : 4'd0);", "t_cnt[wb_cid] <= t_cnt[wb_cid] + ((pushed && ev_cid == wb_cid) ? 4'd1 : 4'd0);"),
 (RTL, "a push in the cycle of a write-back for the same connection is lost", "t_cnt[wb_cid] <= t_cnt[wb_cid] - 4'd1 + ((pushed && ev_cid == wb_cid) ? 4'd1 : 4'd0);", "t_cnt[wb_cid] <= t_cnt[wb_cid] - 4'd1;"),
 (RTL, "a push in that cycle is counted twice", "t_cnt[wb_cid] <= t_cnt[wb_cid] - 4'd1 + ((pushed && ev_cid == wb_cid) ? 4'd1 : 4'd0);", "t_cnt[wb_cid] <= t_cnt[wb_cid] - 4'd1 + ((pushed && ev_cid == wb_cid) ? 4'd2 : 4'd0);"),
 (RTL, "the write-back goes to the event's connection", "t_cnt[wb_cid] <= t_cnt[wb_cid]", "t_cnt[ev_cid] <= t_cnt[wb_cid]"),
 (RTL, "the write pointer does not wrap", "wr <= (wr == PTRW'(DEPTH - 1)) ? '0 : wr + PTRW'(1);", "wr <= wr + PTRW'(1);"),
 (RTL, "the read pointer does not wrap", "rd <= (rd == PTRW'(DEPTH - 1)) ? '0 : rd + PTRW'(1);", "rd <= rd + PTRW'(1);"),
 (RTL, "a pop of an empty FIFO is honoured", "pop_ok = pq_pop && pq_valid;", "pop_ok = pq_pop;"),
 (RTL, "the FIFO count ignores pops", "count <= count + CNTW'(pushed) - CNTW'(pop_ok);", "count <= count + CNTW'(pushed);"),
 (RTL, "the FIFO count ignores pushes", "count <= count + CNTW'(pushed) - CNTW'(pop_ok);", "count <= count - CNTW'(pop_ok);"),
 (RTL, "the head shown is the last entry written", "pq_data = mem[rd];", "pq_data = mem[wr];"),
 (RTL, "the FIFO reads empty one entry late", "pq_valid = (count != '0);", "pq_valid = (count > CNTW'(1));"),
 (RTL, "the connection counts are not reset", "t_pas[i] <= 1'b0; t_una[i] <= 32'd0; t_nxt[i] <= 32'd0; t_rcv[i] <= 32'd0; t_cnt[i] <= 4'd0; end", "t_pas[i] <= 1'b0; t_una[i] <= 32'd0; t_nxt[i] <= 32'd0; t_rcv[i] <= 32'd0; end"),
 (RTL, "the states are not reset", "t_st[i] <= 4'd0; t_pas", "t_pas"),
 (RTL, "the FIFO is not reset", "count <= '0; rd <= '0; wr <= '0;", "rd <= '0; wr <= '0;"),
 (MOD, "model: pending events do not stop the hot path", "self.cnt[ev[\"cid\"]] == 0 and G.fast_path", "G.fast_path"),
 (MOD, "model: the first flag is always 0", "first=1 if self.cnt[c] == 0 else 0", "first=0"),
 (MOD, "model: the first flag is always 1", "first=1 if self.cnt[c] == 0 else 0", "first=1"),
 (MOD, "model: the snapshot is empty", "snap = (t.state, t.passive, t.una, t.nxt, t.rcv); self.fifo.append", "snap = (0, 0, 0, 0, 0); self.fifo.append"),
 (MOD, "model: the write-back does not write RCV.NXT", "t.una, t.nxt, t.rcv = wb[\"st\"], wb[\"pas\"], wb[\"una\"], wb[\"nxt\"], wb[\"rcv\"]", "t.una, t.nxt = wb[\"st\"], wb[\"pas\"], wb[\"una\"], wb[\"nxt\"]"),
 (MOD, "model: the write-back does not decrement the count", "self.cnt[wb[\"cid\"]] -= 1", "pass"),
 (MOD, "model: POLICY 0 never holds", "if ev is None or self.policy != 0: return True", "return True"),
 (MOD, "model: the FIFO is last in, first out", "if popped: self.fifo.popleft()", "if popped: self.fifo.pop()"),
 (MOD, "model: the software keeps no state between entries", "tcb = self.tcb.setdefault(c, G.TCB())", "tcb = G.TCB()"),
 (MOD, "model: the software skips its application commands", "tx, dlv = tcb.event(head[\"e\"], head.get(\"f\", 0)", "tx, dlv = (None, 0) if head[\"e\"] == G.E_CLOSE else tcb.event(head[\"e\"], head.get(\"f\", 0)"),
]
def rtl_battery(root):
    import split_gold as S, tcp_gold as G
    def rows(r, cidw, depth, policy):
        n = S.write_stim(os.path.join(root, "out", "split_stim.hex"), r, cidw)
        o = hw.sim_icarus(["rtl/split.sv", "rtl/tcp.sv", "tb/split_tb.sv"], "split_tb", root=root, defines=(f"NC={n}", f"CIDW={cidw}", f"DEPTH={depth}", f"POLICY={policy}"))[1]
        try: return [tuple(l.split()[1:]) for l in o.splitlines() if l.startswith("C ")]
        except ValueError: return [("x",)]
    for kind in ("realistic", "random", "directed"):
        for cidw, depth, policy, lat in ((2, 4, 0, 6), (2, 2, 0, 24), (3, 4, 1, 12), (2, 3, 1, 3), (3, 8, 0, 1)):
            ncid = 1 << cidw
            if kind == "realistic": ev = S.with_decoys(G.realistic_events(31, conns=ncid, per_conn=25, p_odd=0.06), ncid)
            elif kind == "random": ev = G.gen_events(32, 250, cids=ncid)
            else: ev = S.with_decoys(G.directed_events(0) + G.gen_events(33, 60, cids=ncid), ncid)
            rg = random.Random(depth); r = S.run(ev, ncid, depth, policy, lat=lat, gaps=[rg.randint(0, 2) for _ in ev], seed=depth, record=True, spurious=0.25 if depth in (2, 3) else 0.0)
            if rows(r, cidw, depth, policy) != [tuple(str(x) for x in e) for e in S.expected_rows(r, cidw)]: return f"{kind}, CIDW {cidw}, depth {depth}, policy {policy}, latency {lat}"
    return None
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut15_")
    for sub in ("rtl", "tb", "out", "model"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try:
        if f == RTL: r = rtl_battery(d)
        else:
            q = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'model'); import split_gold as S; print('RESULT', S.battery())"], cwd=d, capture_output=True, text=True, timeout=300)
            o = q.stdout.strip().splitlines()[-1].replace("RESULT ", "") if q.stdout.strip() else "crash"; r = None if o == "None" else o
    except subprocess.TimeoutExpired: r = "hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); return label, ("NOT CAUGHT" if r is None else "caught by: " + r)
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    sys.path.insert(0, os.path.join(flow.ROOT, "model")); import split_gold as S0
    base = rtl_battery(flow.ROOT); b2 = S0.battery(); print("unmutated RTL passes its battery:", base is None, "" if base is None else base); print("unmutated model passes its battery:", b2 is None, "" if b2 is None else b2)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    nr = sum(1 for m in MUT if m[0] == RTL); caught = [0, 0]
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); caught[0 if f == RTL else 1] += st.startswith("caught")
    print(f"RTL mutants caught: {caught[0]} of {nr}; model mutants caught: {caught[1]} of {len(MUT) - nr}")
    sys.exit(0 if base is None and b2 is None and sum(caught) == len(MUT) else 1)
