#!/usr/bin/env python3
"""Chapter 27: test the tests. Three batteries. (1) mutants of the supervisor and the reset generator (rtl/sup.sv), battery `ch27_sup.py --battery` (against model/sup_gold.py: four parameter sets, four scenarios, Icarus). (2) mutants of the glue (rtl/safe.sv) and of the taps added to rtl/w2w.sv, battery `ch27_run.py --battery` (the supervised design against its model on fifteen scenarios, Icarus). (3) mutants of the two models, batteries `--battery-model` (their hand-checked scenarios). The units inside (Chapters 16 to 26) were mutation-tested in their own chapters and are not mutated again."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
SUP = "rtl/sup.sv"; SAFE = "rtl/safe.sv"; W2W = "rtl/w2w.sv"; MSUP = "model/sup_gold.py"; MSAFE = "model/safe_gold.py"
BATT = {SUP: "ch27_sup.py", SAFE: "ch27_run.py", W2W: "ch27_run.py", MSUP: "ch27_sup.py", MSAFE: "ch27_run.py"}
MUT = [
 (SUP, 'INIT lasts one cycle too long', "if (cnt + 1'b1 >= CW'(WARM)) state <= READY;", "if (cnt + 1'b1 > CW'(WARM)) state <= READY;"),
 (SUP, 'INIT lasts one cycle too short', "if (cnt + 1'b1 >= CW'(WARM)) state <= READY;", "if (cnt + 1'b1 >= CW'(WARM - 1)) state <= READY;"),
 (SUP, 'a go needs no ACTIVE session', 'READY: if (go && sess == ACTIVE) state <= RUN;', 'READY: if (go) state <= RUN;'),
 (SUP, 'READY starts RUN by itself', 'READY: if (go && sess == ACTIVE) state <= RUN;', 'READY: if (sess == ACTIVE) state <= RUN;'),
 (SUP, 'the feed watchdog is one cycle late', "wire f_t = (fc >= CW'(FT))", "wire f_t = (fc > CW'(FT))"),
 (SUP, 'the feed watchdog is one cycle early', "wire f_t = (fc >= CW'(FT))", "wire f_t = (fc >= CW'(FT - 1))"),
 (SUP, 'a byte does not restart the feed count', "fc <= feed ? '0 : fc + 1'b1;", "fc <= fc + 1'b1;"),
 (SUP, 'the stall watchdog is one cycle late', "s_t = (sc >= CW'(ST))", "s_t = (sc > CW'(ST))"),
 (SUP, 'the stall watchdog is one cycle early', "s_t = (sc >= CW'(ST))", "s_t = (sc >= CW'(ST - 1))"),
 (SUP, 'a free slot does not restart the stall count', "sc <= slot ? sc + 1'b1 : '0;", "sc <= slot ? sc + 1'b1 : sc;"),
 (SUP, "the tracker's fault is ignored", 'x_f = fault,', "x_f = 1'b0,"),
 (SUP, 'a dead session is ignored', 'x_s = (sess != ACTIVE),', "x_s = 1'b0,"),
 (SUP, 'the external trip is ignored', 'x_t = trip;', "x_t = 1'b0;"),
 (SUP, 'the causes are not latched together', "if (now != 5'd0) begin state <= SAFE; cause <= now; end", "if (now != 5'd0) begin state <= SAFE; cause <= now & (~now + 5'd1); end"),
 (SUP, 'the cause is not kept', "if (now != 5'd0) begin state <= SAFE; cause <= now; end", "if (now != 5'd0) begin state <= SAFE; end"),
 (SUP, 'kill is low in INIT', 'assign kill = (state != RUN);', 'assign kill = (state != RUN) && (state != INIT);'),
 (SUP, 'kill is low in READY', 'assign kill = (state != RUN);', 'assign kill = (state != RUN) && (state != READY);'),
 (SUP, 'kill is low in SAFE', 'assign kill = (state != RUN);', 'assign kill = (state != RUN) && (state != SAFE);'),
 (SUP, 'the logout waits for no quiet', 'tx_ready && quiet;', 'tx_ready;'),
 (SUP, 'the logout waits for no transmitter', '(sess == ACTIVE) && tx_ready && quiet;', '(sess == ACTIVE) && quiet;'),
 (SUP, 'the logout is offered on a dead session', '(state == SAFE) && !sent && (sess == ACTIVE) &&', '(state == SAFE) && !sent &&'),
 (SUP, 'the logout is offered again', "default: if (cq_valid) sent <= 1'b1;", "default: sent <= 1'b0;"),
 (SUP, 'the logout is never counted as sent', "default: if (cq_valid) sent <= 1'b1;", 'default: ;'),
 (SUP, 'reset leaves the state', "if (rst) begin state <= INIT; cnt <= '0;", "if (rst) begin cnt <= '0;"),
 (SUP, 'reset leaves the warm-up count', "state <= INIT; cnt <= '0; fc <= '0;", "state <= INIT; fc <= '0;"),
 (SUP, 'reset leaves the sent flag', "sc <= '0; sent <= 1'b0; cause <= '0; end", "sc <= '0; cause <= '0; end"),
 (SUP, 'reset leaves the cause', "sent <= 1'b0; cause <= '0; end", "sent <= 1'b0; end"),
 (SUP, 'the reset stretch is one cycle short', "if (r2) cnt <= ($bits(cnt))'(RSTN);", "if (r2) cnt <= ($bits(cnt))'(RSTN - 1);"),
 (SUP, 'the reset release is not synchronised', "assign rst_u = r2 || (cnt != '0);", "assign rst_u = rst_in || (cnt != '0);"),
 (SUP, 'the stretch is not restarted by a second pulse', "if (r2) cnt <= ($bits(cnt))'(RSTN); else if (cnt", "if (cnt == '0 && r2) cnt <= ($bits(cnt))'(RSTN); else if (cnt"),
 (SUP, 'the reset ignores the synchroniser', "assign rst_u = r2 || (cnt != '0);", "assign rst_u = r1 || (cnt != '0);"),
 (SAFE, "the supervisor's kill is ignored", '.ext_kill(ext_kill || sup_kill)', '.ext_kill(ext_kill)'),
 (SAFE, "the control plane's kill is ignored", '.ext_kill(ext_kill || sup_kill)', '.ext_kill(sup_kill)'),
 (SAFE, 'the logout request is not offered', '.cq_valid(cq_valid || sup_cq)', '.cq_valid(cq_valid)'),
 (SAFE, 'the logout is the wrong request', ".cq_kind(sup_cq ? 3'd4 : cq_kind)", ".cq_kind(sup_cq ? 3'd3 : cq_kind)"),
 (SAFE, "the control plane's request is lost", '.cq_valid(cq_valid || sup_cq)', '.cq_valid(sup_cq)'),
 (SAFE, 'the supervisor does not see the feed', '.feed(s_valid)', ".feed(1'b0)"),
 (SAFE, 'the supervisor sees the wrong slot', '.slot(tap_slot)', ".slot(1'b0)"),
 (SAFE, 'the supervisor does not see the fault', '.fault(tap_fault)', ".fault(1'b0)"),
 (SAFE, 'the supervisor sees a session that is always active', '.sess(tap_sess)', ".sess(3'd2)"),
 (SAFE, 'the supervisor does not wait for the transmitter', '.tx_ready(tap_txready)', ".tx_ready(1'b1)"),
 (SAFE, 'the supervisor does not wait for quiet', '.quiet(tap_quiet)', ".quiet(1'b1)"),
 (SAFE, 'the supervisor is not reset by the generator', 'sup #(.FT(FT), .ST(ST), .WARM(WARM)) sv (.clk(clk), .rst(rst_u),', 'sup #(.FT(FT), .ST(ST), .WARM(WARM)) sv (.clk(clk), .rst(rst_in),'),
 (SAFE, 'the units are reset by the raw input', '.clk(clk), .rst(rst_u), .s_valid(s_valid)', '.clk(clk), .rst(rst_in), .s_valid(s_valid)'),
 (W2W, 'the slot tap is the queue', 'assign tap_slot = slot;', "assign tap_slot = (fcnt != '0);"),
 (W2W, 'the fault tap is wrong', 'assign tap_fault = t_fault;', "assign tap_fault = 1'b0;"),
 (W2W, 'the quiet tap ignores a held order', '&& !snd_hold && !d_valid;', '&& !d_valid;'),
 (W2W, 'the quiet tap ignores an answer being sent', '&& !snd_hold && !d_valid;', '&& !snd_hold;'),
 (W2W, 'the quiet tap ignores the lifecycle', "assign tap_quiet = (st_o == 3'd0) &&", "assign tap_quiet = 1'b1 &&"),
 (W2W, 'the ready tap is always ready', 'assign tap_txready = tx_ready;', "assign tap_txready = 1'b1;"),
 (W2W, "the session tap is the transmitter's expected sequence", 'assign tap_sess = ostate;', 'assign tap_sess = oexp[2:0];'),
 (MSUP, 'model: INIT is one cycle short', 'if self.cnt >= self.warm: self.state = READY', 'if self.cnt >= self.warm - 1: self.state = READY'),
 (MSUP, 'model: the feed trips late', 'f_t = self.fc >= self.ft;', 'f_t = self.fc > self.ft;'),
 (MSUP, 'model: the stall trips early', 's_t = self.sc >= self.st', 's_t = self.sc >= self.st - 1'),
 (MSUP, 'model: a go needs no session', 'if go and sess == ACTIVE: self.state = RUN', 'if go: self.state = RUN'),
 (MSUP, 'model: the logout needs no quiet', 'and tx_ready and quiet)', 'and tx_ready)'),
 (MSUP, 'model: the logout is repeated', '            if cq: self.sent = 1', '            pass'),
 (MSUP, 'model: the reset stretch is short', 'if self.r2: self.cnt = self.rstn', 'if self.r2: self.cnt = self.rstn - 1'),
 (MSAFE, "model: the supervisor's kill is ignored", 'if o[1] or cy.get("kill"): cy2["kill"] = 1', 'if cy.get("kill"): cy2["kill"] = 1'),
 (MSAFE, 'model: the logout is not offered', 'if o[2]: cy2["cq"] = SS.LOGOUT', 'if False: cy2["cq"] = SS.LOGOUT'),
 (MSAFE, 'model: the supervisor sees no feed', 'feed = int(cy.get("s", (0,))[0] != 0)', 'feed = 0'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut27_")
    for sub in ("rtl", "tb", "out", "model", "tools", "formal"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "t1[0-9]_*", "t2[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if s.count(old) != 1: shutil.rmtree(d, ignore_errors=True); return label, f"BAD ANCHOR ({s.count(old)} occurrences)"
    open(p, "w").write(s.replace(old, new))
    try: q = subprocess.run([sys.executable, "tools/" + BATT[f], "--battery-model" if f.startswith("model") else "--battery"], cwd=d, capture_output=True, text=True, timeout=1500); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the models. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    base = all(subprocess.run([sys.executable, "tools/" + b, a], cwd=flow.ROOT, capture_output=True, text=True).stdout.strip().endswith("None") for b, a in (("ch27_sup.py", "--battery"), ("ch27_run.py", "--battery"), ("ch27_sup.py", "--battery-model"), ("ch27_run.py", "--battery-model")))
    print("unmutated designs and models pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); c = cnt.setdefault(f, [0, 0]); c[1] += 1; c[0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
