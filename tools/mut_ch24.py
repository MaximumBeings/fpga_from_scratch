#!/usr/bin/env python3
"""Chapter 24: test the tests. Two families. (1) mutants of rtl/sess.sv, battery `ch24_run.py --battery`: the transmitter against the cycle model, every beat, the state, the expected sequence number, `ready` and the answers in the cycle the model says, five formats, on eight session scenarios. (2) mutants of model/sess_gold.py, battery `--battery-model`: the model's own hand-checked scenarios, the bytes of every packet written out by hand and the timelines worked out cycle by cycle (the model is the oracle; what checks IT is a handful of cases worked by hand, so this family measures how complete they are)."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/sess.sv"; MOD = "model/sess_gold.py"
MUT = [
 (RTL, 'a heartbeat does not stop a request', 'assign in_ready = tx_free && !hb_due;', 'assign in_ready = tx_free;'),
 (RTL, 'the transmitter is free only when empty', "wire tx_free = (txlen <= 6'(W));", "wire tx_free = (txlen < 6'(W));"),
 (RTL, 'the transmitter is free one beat early', "wire tx_free = (txlen <= 6'(W));", "wire tx_free = (txlen <= 6'(2 * W));"),
 (RTL, 'the byte count of a full beat is zero', "assign o_nb = tx_free ? 4'(txlen) : 4'(W);", "assign o_nb = tx_free ? 4'(txlen) : 4'(0);"),
 (RTL, 'the byte count of the last beat is W', "assign o_nb = tx_free ? 4'(txlen) : 4'(W);", "assign o_nb = 4'(W);"),
 (RTL, 'the beat is taken from the wrong end', 'assign o_data = tx[255 -: 8*W];', 'assign o_data = tx[247 -: 8*W];'),
 (RTL, 'a sell is sent as a buy', "wire [7:0] side_c = in_side ? 8'h53 : 8'h42;", "wire [7:0] side_c = in_side ? 8'h42 : 8'h53;"),
 (RTL, 'the order length is wrong', "16'h001D, 8'h55, 8'h4F, in_tok", "16'h001C, 8'h55, 8'h4F, in_tok"),
 (RTL, 'the order type is wrong', "16'h001D, 8'h55, 8'h4F, in_tok", "16'h001D, 8'h55, 8'h50, in_tok"),
 (RTL, 'the order has no data marker', "16'h001D, 8'h55, 8'h4F, in_tok", "16'h001D, 8'h00, 8'h4F, in_tok"),
 (RTL, 'the order token is the new token', "8'h4F, in_tok, side_c, in_shares, stk, in_px, in_tif, firm", "8'h4F, in_tok2, side_c, in_shares, stk, in_px, in_tif, firm"),
 (RTL, 'the order shares are the price', 'side_c, in_shares, stk, in_px, in_tif, firm', 'side_c, in_px, stk, in_px, in_tif, firm'),
 (RTL, 'the order price is the shares', 'in_shares, stk, in_px, in_tif, firm, display', 'in_shares, stk, in_shares, in_tif, firm, display'),
 (RTL, 'the order tif is the price', 'stk, in_px, in_tif, firm, display, capacity', 'stk, in_px, in_px, firm, display, capacity'),
 (RTL, 'the order stock is the firm', 'side_c, in_shares, stk, in_px', 'side_c, in_shares, firm, in_px'),
 (RTL, 'the order firm is the stock', "in_tif, firm, display, capacity, 8'h00", "in_tif, stk, display, capacity, 8'h00"),
 (RTL, 'the order display and capacity are swapped', "firm, display, capacity, 8'h00", "firm, capacity, display, 8'h00"),
 (RTL, 'the order stock is always symbol 0', 'stock[in_sym[$clog2(NS > 1 ? NS : 2)-1:0]]', 'stock[0]'),
 (RTL, 'the cancel length is wrong', "16'h000A, 8'h55, 8'h58", "16'h0009, 8'h55, 8'h58"),
 (RTL, 'the cancel type is wrong', "16'h000A, 8'h55, 8'h58", "16'h000A, 8'h55, 8'h59"),
 (RTL, 'the cancel shares are the price', "8'h58, in_tok, in_shares, 160'd0", "8'h58, in_tok, in_px, 160'd0"),
 (RTL, 'the cancel token is the new token', "8'h58, in_tok, in_shares, 160'd0", "8'h58, in_tok2, in_shares, 160'd0"),
 (RTL, 'the replace length is wrong', "16'h0017, 8'h55, 8'h4E", "16'h0016, 8'h55, 8'h4E"),
 (RTL, 'the replace type is wrong', "16'h0017, 8'h55, 8'h4E", "16'h0017, 8'h55, 8'h52"),
 (RTL, 'the replace tokens are swapped', "8'h4E, in_tok, in_tok2, in_shares", "8'h4E, in_tok2, in_tok, in_shares"),
 (RTL, 'the replace price and shares are swapped', "in_tok2, in_shares, in_px, in_tif, display, 56'd0", "in_tok2, in_px, in_shares, in_tif, display, 56'd0"),
 (RTL, 'the replace has no display', "in_px, in_tif, display, 56'd0", "in_px, in_tif, capacity, 56'd0"),
 (RTL, 'the login length is wrong', "16'h000D, 8'h4C", "16'h000C, 8'h4C"),
 (RTL, 'the login type is wrong', "16'h000D, 8'h4C", "16'h000D, 8'h4D"),
 (RTL, 'the login user and password are swapped', "8'h4C, user, pw, reqseq", "8'h4C, pw, user, reqseq"),
 (RTL, 'the login has no sequence number', "8'h4C, user, pw, reqseq, 136'd0", "8'h4C, user, pw, 32'd0, 136'd0"),
 (RTL, 'the heartbeat type is wrong', "wire [255:0] p_hb      = {16'h0001, 8'h52, 232'd0};", "wire [255:0] p_hb      = {16'h0001, 8'h48, 232'd0};"),
 (RTL, 'the logout type is wrong', "wire [255:0] p_logout  = {16'h0001, 8'h4F, 232'd0};", "wire [255:0] p_logout  = {16'h0001, 8'h52, 232'd0};"),
 (RTL, 'an order is one byte short', "K_ORDER: begin pk = p_order; pklen = 6'd31; end", "K_ORDER: begin pk = p_order; pklen = 6'd30; end"),
 (RTL, 'a cancel is one byte short', "pk = p_cancel; pklen = 6'd12;", "pk = p_cancel; pklen = 6'd11;"),
 (RTL, 'a replace is one byte long', "pk = p_replace; pklen = 6'd25;", "pk = p_replace; pklen = 6'd26;"),
 (RTL, 'a login is one byte short', "pk = p_login; pklen = 6'd15;", "pk = p_login; pklen = 6'd14;"),
 (RTL, 'a logout is longer than a heartbeat', "default: begin pk = p_logout; pklen = 6'd3; end", "default: begin pk = p_logout; pklen = 6'd4; end"),
 (RTL, 'a heartbeat is one byte short', "pk = p_hb; pklen = 6'd3;", "pk = p_hb; pklen = 6'd2;"),
 (RTL, 'a login is allowed when active', '(in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE)', '(in_kind == K_LOGIN) ? (st == IDLE || st == ACTIVE) : (st == ACTIVE)'),
 (RTL, 'a login is allowed after a rejection', '(in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE)', '(in_kind == K_LOGIN) ? (st == IDLE || st == REJECTED) : (st == ACTIVE)'),
 (RTL, 'orders are allowed while logging in', '(in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE)', '(in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE || st == LOGIN)'),
 (RTL, 'orders are allowed after a gap', '(in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE)', '(in_kind == K_LOGIN) ? (st == IDLE) : (st == ACTIVE || st == GAP)'),
 (RTL, 'a symbol equal to NS is allowed', "wire badsym = (in_kind == K_ORDER) && (in_sym >= 4'(NS));", "wire badsym = (in_kind == K_ORDER) && (in_sym > 4'(NS));"),
 (RTL, 'a replace with a bad symbol is refused', "wire badsym = (in_kind == K_ORDER) && (in_sym >= 4'(NS));", "wire badsym = (in_kind != K_LOGIN) && (in_sym >= 4'(NS));"),
 (RTL, 'a bad symbol is sent anyway', 'wire load_req = accept && allowed && !badsym && (in_kind <= K_LOGOUT);', 'wire load_req = accept && allowed && (in_kind <= K_LOGOUT);'),
 (RTL, 'the answer is valid for every offer', 'rv <= accept;', 'rv <= in_valid;'),
 (RTL, 'a refusal is reported as accepted', "res <= !allowed ? 2'd1 : (badsym ? 2'd2 : 2'd0);", "res <= 2'd0;"),
 (RTL, 'a bad symbol is reported as refused', "res <= !allowed ? 2'd1 : (badsym ? 2'd2 : 2'd0);", "res <= !allowed ? 2'd1 : (badsym ? 2'd1 : 2'd0);"),
 (RTL, 'a login is not heard accepted', "if (st == LOGIN && rx_type == 8'h41) begin nst = ACTIVE; nexp = rx_seq; end", "if (st == LOGIN && rx_type == 8'h41) begin nst = ACTIVE; end"),
 (RTL, 'the accepted login takes the wrong sequence number', 'nst = ACTIVE; nexp = rx_seq; end', "nst = ACTIVE; nexp = rx_seq + 1'b1; end"),
 (RTL, 'a login is accepted from any state', "if (st == LOGIN && rx_type == 8'h41)", "if (rx_type == 8'h41)"),
 (RTL, 'a rejection is ignored', "else if (st == LOGIN && rx_type == 8'h4A) nst = REJECTED;", "else if (st == LOGIN && rx_type == 8'h4A) nst = LOGIN;"),
 (RTL, 'a rejection goes to dead', "else if (st == LOGIN && rx_type == 8'h4A) nst = REJECTED;", "else if (st == LOGIN && rx_type == 8'h4A) nst = DEAD;"),
 (RTL, 'an end of session is ignored while logging in', "else if (rx_type == 8'h5A && (st == LOGIN || st == ACTIVE)) nst = CLOSED;", "else if (rx_type == 8'h5A && st == ACTIVE) nst = CLOSED;"),
 (RTL, 'an end of session is ignored while active', "else if (rx_type == 8'h5A && (st == LOGIN || st == ACTIVE)) nst = CLOSED;", "else if (rx_type == 8'h5A && st == LOGIN) nst = CLOSED;"),
 (RTL, 'an end of session closes any state', "else if (rx_type == 8'h5A && (st == LOGIN || st == ACTIVE)) nst = CLOSED;", "else if (rx_type == 8'h5A) nst = CLOSED;"),
 (RTL, 'a server heartbeat is not heard', "else if (st == ACTIVE && rx_type == 8'h48) heard = 1'b1;", "else if (st == ACTIVE && rx_type == 8'h48) heard = 1'b0;"),
 (RTL, 'a sequenced packet in order is not counted', "begin nexp = expseq + 1'b1; heard = 1'b1; end", "begin nexp = expseq; heard = 1'b1; end"),
 (RTL, 'a sequenced packet in order is not heard', "begin nexp = expseq + 1'b1; heard = 1'b1; end", "begin nexp = expseq + 1'b1; heard = 1'b0; end"),
 (RTL, 'a number ahead is accepted', 'if (rx_seq == expseq) begin', 'if (rx_seq >= expseq) begin'),
 (RTL, 'a number behind is accepted', 'if (rx_seq == expseq) begin', 'if (rx_seq <= expseq) begin'),
 (RTL, 'a gap is not noticed', 'end else nst = GAP; end', 'end else nst = ACTIVE; end'),
 (RTL, 'the login timer is one cycle long', "if (st == LOGIN && nst == LOGIN && ltc + 1'b1 >= TW'(TL)) nst = DEAD;", "if (st == LOGIN && nst == LOGIN && ltc + 1'b1 > TW'(TL)) nst = DEAD;"),
 (RTL, 'the login timer is one cycle short', "if (st == LOGIN && nst == LOGIN && ltc + 1'b1 >= TW'(TL)) nst = DEAD;", "if (st == LOGIN && nst == LOGIN && ltc >= TW'(TL)) nst = DEAD;"),
 (RTL, 'the quiet limit is twice the heartbeat', "rxc + 1'b1 >= TW'(3 * HB)) nst = DEAD;", "rxc + 1'b1 >= TW'(2 * HB)) nst = DEAD;"),
 (RTL, 'the quiet limit is four heartbeats', "rxc + 1'b1 >= TW'(3 * HB)) nst = DEAD;", "rxc + 1'b1 >= TW'(4 * HB)) nst = DEAD;"),
 (RTL, 'a packet heard does not save the session', 'if (st == ACTIVE && nst == ACTIVE && !heard && rxc', 'if (st == ACTIVE && nst == ACTIVE && rxc'),
 (RTL, 'the login timer is not counted', "if (st == LOGIN && nst == LOGIN) ltc <= ltc + 1'b1;", 'if (st == LOGIN && nst == LOGIN) ltc <= ltc;'),
 (RTL, 'the quiet counter is not restarted by a packet', "rxc <= heard ? '0 : rxc + 1'b1;", "rxc <= rxc + 1'b1;"),
 (RTL, 'a heartbeat is due one cycle late', "wire hb_due = (st == ACTIVE) && (hbc >= TW'(HB));", "wire hb_due = (st == ACTIVE) && (hbc > TW'(HB));"),
 (RTL, 'a heartbeat is due one cycle early', "wire hb_due = (st == ACTIVE) && (hbc >= TW'(HB));", "wire hb_due = (st == ACTIVE) && (hbc >= TW'(HB - 1));"),
 (RTL, 'a request does not restart the heartbeat count', "hbc <= (loaded || st != ACTIVE) ? '0 : hbc + 1'b1;", "hbc <= (load_hb || st != ACTIVE) ? '0 : hbc + 1'b1;"),
 (RTL, 'the heartbeat count is not cleared outside ACTIVE', "hbc <= (loaded || st != ACTIVE) ? '0 : hbc + 1'b1;", "hbc <= (loaded) ? '0 : hbc + 1'b1;"),
 (RTL, 'a logout does not close the session', 'else if (load_req && in_kind == K_LOGOUT) st <= CLOSED;', 'else if (load_req && in_kind == K_LOGOUT) st <= nst;'),
 (RTL, 'a heartbeat is not sent when the transmitter is free', 'wire load_hb = hb_due && tx_free;', 'wire load_hb = hb_due && (txlen == 0);'),
 (RTL, 'the transmitter is not advanced', "else begin tx <= tx << (8 * W); txlen <= tx_free ? 6'd0 : txlen - 6'(W); end", "else begin tx <= tx; txlen <= tx_free ? 6'd0 : txlen - 6'(W); end"),
 (RTL, 'the transmitter advances one byte', 'else begin tx <= tx << (8 * W); txlen <=', 'else begin tx <= tx << 8; txlen <='),
 (RTL, 'the length is not reduced', "txlen <= tx_free ? 6'd0 : txlen - 6'(W);", "txlen <= tx_free ? 6'd0 : txlen;"),
 (RTL, 'the length is reduced by one', "txlen <= tx_free ? 6'd0 : txlen - 6'(W);", "txlen <= tx_free ? 6'd0 : txlen - 6'd1;"),
 (RTL, 'a stock write ignores the symbol', "3'd0: for (int i = 0; i < NS; i++) if (cfg_sym == 4'(i)) stock[i] <= cfg_data;", "3'd0: for (int i = 0; i < NS; i++) stock[i] <= cfg_data;"),
 (RTL, 'a user write goes to the password', "3'd1: user <= cfg_data;", "3'd1: pw <= cfg_data;"),
 (RTL, 'a password write is ignored', "3'd2: pw <= cfg_data;", "3'd2: ;"),
 (RTL, 'a firm write is ignored', "3'd3: firm <= cfg_data;", "3'd3: ;"),
 (RTL, 'display and capacity are swapped', 'begin display <= cfg_data[15:8]; capacity <= cfg_data[7:0]; end', 'begin display <= cfg_data[7:0]; capacity <= cfg_data[15:8]; end'),
 (RTL, 'a sequence number write is ignored', "3'd5: reqseq <= cfg_data;", "3'd5: ;"),
 (RTL, 'reset does not clear the state', "if (rst) begin st <= IDLE; expseq <= '0; rxc <= '0; ltc <= '0; txlen <= '0; rv <= 1'b0; res <= '0; end", "if (rst) begin expseq <= '0; rxc <= '0; ltc <= '0; txlen <= '0; rv <= 1'b0; res <= '0; end"),
 (RTL, 'reset does not clear the transmitter', "ltc <= '0; txlen <= '0; rv <= 1'b0;", "ltc <= '0; rv <= 1'b0;"),
 (RTL, 'reset does not clear the expected number', "expseq <= '0; rxc <= '0;", "rxc <= '0;"),
 (RTL, 'reset does not clear the answer flag', "txlen <= '0; rv <= 1'b0; res <= '0; end", "txlen <= '0; res <= '0; end"),
 (RTL, 'reset does not clear the stock names', "for (int i = 0; i < NS; i++) stock[i] <= '0;", "for (int i = 0; i < 0; i++) stock[i] <= '0;"),
 (RTL, 'reset does not clear the user', "user <= '0; pw <= '0; firm <= '0;", "pw <= '0; firm <= '0;"),
 (RTL, 'reset does not clear the firm', "user <= '0; pw <= '0; firm <= '0;", "user <= '0; pw <= '0;"),
 (RTL, 'reset does not clear the sequence number', "reqseq <= '0; display <= '0;", "display <= '0;"),
 (RTL, 'reset does not clear the display', "display <= '0; capacity <= '0;", "capacity <= '0;"),
 (MOD, 'model: a sell is a buy', '(b"S" if r["side"] else b"B")', '(b"B" if r["side"] else b"S")'),
 (MOD, 'model: the order length is wrong', 'return be(len(body), 2) + body', 'return be(len(body) + (1 if body[:2] == b"UO" else 0), 2) + body'),
 (MOD, 'model: the heartbeat comes one cycle late', 'hb_due = st == ACTIVE and hbc >= hb', 'hb_due = st == ACTIVE and hbc > hb'),
 (MOD, 'model: ready ignores the heartbeat', 'ready = 1 if (len(tx) <= w and not hb_due) else 0', 'ready = 1 if len(tx) <= w else 0'),
 (MOD, 'model: ready needs an empty transmitter', 'ready = 1 if (len(tx) <= w and not hb_due) else 0', 'ready = 1 if (len(tx) == 0 and not hb_due) else 0'),
 (MOD, 'model: a login is allowed when active', 'allowed = (st == IDLE) if kind == LOGINQ else (st == ACTIVE)', 'allowed = (st in (IDLE, ACTIVE)) if kind == LOGINQ else (st == ACTIVE)'),
 (MOD, 'model: orders are allowed after a gap', 'allowed = (st == IDLE) if kind == LOGINQ else (st == ACTIVE)', 'allowed = (st == IDLE) if kind == LOGINQ else (st in (ACTIVE, GAP))'),
 (MOD, 'model: a bad symbol is allowed', 'elif kind == ORDER and r["sym"] >= ns: new_ans = BADSYM', 'elif kind == ORDER and r["sym"] > ns: new_ans = BADSYM'),
 (MOD, 'model: the quiet limit is two heartbeats', 'if rxc >= 3 * hb: nst = DEAD', 'if rxc >= 2 * hb: nst = DEAD'),
 (MOD, 'model: the login timer is one cycle long', 'if ltc >= tl: nst = DEAD', 'if ltc > tl: nst = DEAD'),
 (MOD, 'model: a server heartbeat does not count', 'elif st == ACTIVE and t == "H": heard = True', 'elif st == ACTIVE and t == "H": heard = False'),
 (MOD, 'model: a number ahead is accepted', 'if sq == exp: exp = (exp + 1) & M; heard = True', 'if sq >= exp: exp = (exp + 1) & M; heard = True'),
 (MOD, 'model: a gap is not noticed', 'else: nst = GAP', 'else: nst = ACTIVE'),
 (MOD, 'model: the accepted login keeps the old number', 'if st == LOGIN and t == "A": nst = ACTIVE; exp = sq', 'if st == LOGIN and t == "A": nst = ACTIVE'),
 (MOD, 'model: an end of session is ignored while logging in', 'elif t == "Z" and st in (LOGIN, ACTIVE): nst = CLOSED', 'elif t == "Z" and st == ACTIVE: nst = CLOSED'),
 (MOD, 'model: a logout does not close', 'elif acc == LOGOUT: nst = CLOSED', 'elif acc == LOGOUT: pass'),
 (MOD, 'model: a refused request is not answered', 'if not allowed: new_ans = REFUSED', 'if not allowed: new_ans = None'),
 (MOD, 'model: a request does not restart the heartbeat count', 'if nst == ACTIVE: hbc = 0 if (loaded or st != ACTIVE) else hbc + 1', 'if nst == ACTIVE: hbc = 0 if (hb_due or st != ACTIVE) else hbc + 1'),
 (MOD, 'model: a write for a bad symbol overwrites symbol 0', 'if sym < len(cfg["stock"]): cfg["stock"][sym] = be(data, 4)', 'cfg["stock"][sym % len(cfg["stock"])] = be(data, 4)'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut24_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch24_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch24_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch24_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
