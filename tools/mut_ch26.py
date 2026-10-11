#!/usr/bin/env python3
"""Chapter 26: test the tests. Two families. (1) mutants of rtl/w2w.sv (the glue: adapter, queue, slot, strategy, send and reject logic), battery `ch26_run.py --battery`: the whole design against its model, every output of every cycle, on seventeen traffic mixes (twelve generated, five worked by hand), Icarus. (2) mutants of model/w2w_gold.py, battery `--battery-model`: its self-test (the stepped transmitter against model/sess_gold.py on random sessions, and the one scenario worked by hand, with its times). The units inside (parser, book, signal, trigger, gate, tracker, transmitter) were mutation-tested in their own chapters and are not mutated again here."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flow
RTL = "rtl/w2w.sv"; MOD = "model/w2w_gold.py"
MUT = [
 (RTL, 'F (a full add order) is not an ADD', "8'h41, 8'h46: begin ad_ok", "8'h41: begin ad_ok"),
 (RTL, 'the side of an add is inverted', "ad_side = (f_side == 8'h53);", "ad_side = (f_side == 8'h42);"),
 (RTL, 'an add carries no price', "ad_side = (f_side == 8'h53); ad_px = f_price; ad_sh = f_shares;", "ad_side = (f_side == 8'h53); ad_px = 32'd0; ad_sh = f_shares;"),
 (RTL, 'an add carries no shares', "ad_side = (f_side == 8'h53); ad_px = f_price; ad_sh = f_shares;", "ad_side = (f_side == 8'h53); ad_px = f_price; ad_sh = 32'd0;"),
 (RTL, 'an execute is a cancel', "8'h45: begin ad_ok = 1'b1; ad_t = 3'd1;", "8'h45: begin ad_ok = 1'b1; ad_t = 3'd2;"),
 (RTL, 'an execute carries no shares', "ad_t = 3'd1; ad_sh = f_shares; end", "ad_t = 3'd1; end"),
 (RTL, 'a cancel is a delete', "8'h58: begin ad_ok = 1'b1; ad_t = 3'd2;", "8'h58: begin ad_ok = 1'b1; ad_t = 3'd3;"),
 (RTL, 'a cancel carries no shares', "ad_t = 3'd2; ad_sh = f_shares; end", "ad_t = 3'd2; end"),
 (RTL, 'a delete is a cancel', "8'h44: begin ad_ok = 1'b1; ad_t = 3'd3; end", "8'h44: begin ad_ok = 1'b1; ad_t = 3'd2; end"),
 (RTL, 'a replace is an add', "8'h55: begin ad_ok = 1'b1; ad_t = 3'd4;", "8'h55: begin ad_ok = 1'b1; ad_t = 3'd0;"),
 (RTL, 'a replace carries no price', "ad_t = 3'd4; ad_px = f_price; ad_sh = f_shares; end", "ad_t = 3'd4; ad_sh = f_shares; end"),
 (RTL, 'a replace carries no shares', "ad_t = 3'd4; ad_px = f_price; ad_sh = f_shares; end", "ad_t = 3'd4; ad_px = f_price; end"),
 (RTL, 'a symbol equal to NS is traded', "f_locate < 16'(NS)", "f_locate <= 16'(NS)"),
 (RTL, 'messages with an error are queued', "m_valid && m_err == 2'd0 &&", 'm_valid &&'),
 (RTL, 'the queued symbol is always 0', '{ad_t, f_ref[31:0], f_newref[31:0], f_locate[SW-1:0], ad_side, ad_px, ad_sh}', "{ad_t, f_ref[31:0], f_newref[31:0], {SW{1'b0}}, ad_side, ad_px, ad_sh}"),
 (RTL, 'the reference is the high word', '{ad_t, f_ref[31:0],', '{ad_t, f_ref[63:32],'),
 (RTL, 'the new reference is the old one', 'f_newref[31:0], f_locate[SW-1:0]', 'f_ref[31:0], f_locate[SW-1:0]'),
 (RTL, 'the queue is full one entry early', "wire fq_full = (fcnt == ($clog2(QD+1))'(QD));", "wire fq_full = (fcnt == ($clog2(QD+1))'(QD - 1));"),
 (RTL, 'a full queue is overwritten', 'wire fq_push = ad_ok && !fq_full;', 'wire fq_push = ad_ok;'),
 (RTL, 'drops are not counted', "if (ad_ok && fq_full) drops <= drops + 1'b1;", "if (1'b0) drops <= drops + 1'b1;"),
 (RTL, 'the queue count ignores pops', "- ($bits(fcnt))'(bk_acc);", "- ($bits(fcnt))'(1'b0);"),
 (RTL, 'the head pointer does not advance', 'if (bk_acc) fhd <= (fhd', "if (1'b0) fhd <= (fhd"),
 (RTL, 'the strategy slot is ignored', "wire bk_in_valid = (fcnt != '0) && !slot;", "wire bk_in_valid = (fcnt != '0);"),
 (RTL, 'the slot is never freed', "else if (sg_v) slot <= 1'b0;", "else if (1'b0) slot <= 1'b0;"),
 (RTL, 'the trigger sees the wrong event type', 'h_t <= fh[129+SW +: 3];', "h_t <= 3'd0;"),
 (RTL, 'the trigger sees the wrong price', 'h_px <= fh[63:32];', 'h_px <= fh[31:0];'),
 (RTL, 'the trigger sees the wrong shares', 'h_sh <= fh[31:0]; end', 'h_sh <= fh[63:32]; end'),
 (RTL, 'the trigger key is not the symbol', ".in_key({{(32-SW){1'b0}}, h_sym})", ".in_key(32'd0)"),
 (RTL, 'the trigger side is wrong', '.in_side(h_side), .in_px(h_px)', ".in_side(1'b0), .in_px(h_px)"),
 (RTL, 'the signal sees bid and ask swapped', '.in_bpx(bk_bpx[23:0]), .in_bsh(bk_bsh[19:0]), .in_apx(bk_apx[23:0]), .in_ash(bk_ash[19:0])', '.in_bpx(bk_apx[23:0]), .in_bsh(bk_ash[19:0]), .in_apx(bk_bpx[23:0]), .in_ash(bk_bsh[19:0])'),
 (RTL, 'the trigger result is not kept', 'if (tg_v) t_fire <= tg_fire;', "if (tg_v) t_fire <= 1'b1;"),
 (RTL, 'a failed event can trade', "r_okres <= (bk_o_res == 3'd0);", "r_okres <= 1'b1;"),
 (RTL, "the traded symbol is the event's", 'r_sym <= bk_o_sym;', 'r_sym <= h_sym;'),
 (RTL, 'a crossed book can trade (buy)', 'wire dec_buy = sg_v && sg_ok && !sg_cross && !sg_lock', 'wire dec_buy = sg_v && sg_ok && !sg_lock'),
 (RTL, 'a locked book can trade (sell)', 'wire dec_sell = sg_v && sg_ok && !sg_cross && !sg_lock', 'wire dec_sell = sg_v && sg_ok && !sg_cross'),
 (RTL, 'a buy needs no trigger', 'wire dec_buy = sg_v && sg_ok && !sg_cross && !sg_lock && t_fire &&', 'wire dec_buy = sg_v && sg_ok && !sg_cross && !sg_lock &&'),
 (RTL, 'a sell needs no trigger', 'wire dec_sell = sg_v && sg_ok && !sg_cross && !sg_lock && t_fire &&', 'wire dec_sell = sg_v && sg_ok && !sg_cross && !sg_lock &&'),
 (RTL, 'a buy needs no applied event', '!sg_lock && t_fire && r_okres && (sg_imb >=', '!sg_lock && t_fire && (sg_imb >='),
 (RTL, 'a sell needs no applied event', '!sg_lock && t_fire && r_okres && (sg_imb <=', '!sg_lock && t_fire && (sg_imb <='),
 (RTL, 'the buy threshold is strict', "(sg_imb >= $signed((F+2)'(THR)))", "(sg_imb > $signed((F+2)'(THR)))"),
 (RTL, 'the sell threshold is strict', "(sg_imb <= -$signed((F+2)'(THR)))", "(sg_imb < -$signed((F+2)'(THR)))"),
 (RTL, 'the buy threshold is half', "(sg_imb >= $signed((F+2)'(THR)))", "(sg_imb >= $signed((F+2)'(THR / 2)))"),
 (RTL, 'a sell is also taken when imbalance is positive', "(sg_imb <= -$signed((F+2)'(THR)))", "(sg_imb <= $signed((F+2)'(THR)))"),
 (RTL, 'the ask price is the bid', "ask_px = 25'((sg_mid2 + 25'(sg_spread)) >> 1)", "ask_px = 25'((sg_mid2 - 25'(sg_spread)) >> 1)"),
 (RTL, 'the bid price is the ask', "bid_px = 25'((sg_mid2 - 25'(sg_spread)) >> 1)", "bid_px = 25'((sg_mid2 + 25'(sg_spread)) >> 1)"),
 (RTL, 'the order side is wrong', '.ord_side(dec_sell)', '.ord_side(dec_buy)'),
 (RTL, 'the order quantity is wrong', ".ord_qty(16'(OQ))", ".ord_qty(16'(OQ + 1))"),
 (RTL, 'the order account is 1', ".ord_acct(4'd0)", ".ord_acct(4'd1)"),
 (RTL, "the order symbol is the event's", ".ord_sym({{(4-SW){1'b0}}, r_sym})", ".ord_sym({{(4-SW){1'b0}}, h_sym})"),
 (RTL, "the order price is the wrong side's", '.ord_px(dec_sell ? bid_px[15:0] : ask_px[15:0])', '.ord_px(dec_sell ? ask_px[15:0] : bid_px[15:0])'),
 (RTL, 'the token counts offers, not takes', "if (ord_acc) begin tokc <= tokc + 1'b1;", 'if (ord_acc) begin tokc <= tokc;'),
 (RTL, "the sent price is the wrong side's", 'o_px <= dec_sell ? bid_px[15:0] : ask_px[15:0]; end', 'o_px <= dec_sell ? ask_px[15:0] : bid_px[15:0]; end'),
 (RTL, 'the sent side is wrong', 'o_side <= dec_sell;', 'o_side <= dec_buy;'),
 (RTL, "the sent symbol is the event's", "o_sym <= {{(4-SW){1'b0}}, r_sym};", "o_sym <= {{(4-SW){1'b0}}, h_sym};"),
 (RTL, 'missed orders are not counted', "if (ord_valid && !ord_ready) miss <= miss + 1'b1;", "if (1'b0) miss <= miss + 1'b1;"),
 (RTL, 'a held order is forgotten', "wire snd_now = (d_valid && d_res == 5'd0) || snd_hold;", "wire snd_now = (d_valid && d_res == 5'd0);"),
 (RTL, 'every answer is sent', "wire snd_now = (d_valid && d_res == 5'd0) || snd_hold;", 'wire snd_now = d_valid || snd_hold;'),
 (RTL, 'the control request loses to the order', ".in_kind(cq_valid ? cq_kind : 3'd0)", ".in_kind(3'd0)"),
 (RTL, 'the control request is not offered', 'wire tx_in_valid = cq_valid || snd_now;', 'wire tx_in_valid = snd_now;'),
 (RTL, 'the sent token is wrong', '.in_tok(o_tok)', '.in_tok(tokc)'),
 (RTL, 'the sent price is wrong', ".in_px(32'(o_px))", ".in_px(32'd0)"),
 (RTL, 'the sent shares are wrong', ".in_shares(32'(OQ))", ".in_shares(32'(OQ + 1))"),
 (RTL, 'the sent symbol is 0', '.in_sym(o_sym)', ".in_sym(4'd0)"),
 (RTL, 'a control request counts as an order', 'ord_q <= snd_now && tx_ready && !cq_valid;', 'ord_q <= snd_now && tx_ready;'),
 (RTL, 'a refusal is not turned into a reject', "if (rv_ && ord_q && ores != 2'd0) begin rej_pend", "if (1'b0) begin rej_pend"),
 (RTL, 'a refusal count is not kept', "rej_pend <= 1'b1; refused <= refused + 1'b1; end", "rej_pend <= 1'b1; end"),
 (RTL, 'the reject names the wrong token', '.r_tok(r_valid ? r_tok : o_tok)', '.r_tok(r_valid ? r_tok : tokc)'),
 (RTL, 'an exchange report does not win over the reject', ".r_kind(r_valid ? r_kind : 2'd3), .r_tok(r_valid ? r_tok : o_tok), .r_qty(r_valid ? r_qty : 16'd0)", ".r_kind(rej_pend ? 2'd3 : r_kind), .r_tok(rej_pend ? o_tok : r_tok), .r_qty(rej_pend ? 16'd0 : r_qty)"),
 (RTL, 'a waiting reject is lost when a report arrives', "else if (rej_pend && !r_valid) rej_pend <= 1'b0;", "else if (rej_pend) rej_pend <= 1'b0;"),
 (RTL, 'the hold is never set', "if (snd_now && !tx_ready && !cq_valid) snd_hold <= 1'b1;", "if (snd_now && !tx_ready && !cq_valid) snd_hold <= 1'b0;"),
 (RTL, 'the hold is never released', "else if (snd_hold && tx_ready) snd_hold <= 1'b0;", "else if (1'b0) snd_hold <= 1'b0;"),
 (RTL, 'reset leaves the token counter at 0', "tokc <= 32'd1; o_tok", "tokc <= 32'd0; o_tok"),
 (RTL, 'reset leaves the queue count', "if (rst) begin fcnt <= '0; fhd", 'if (rst) begin fhd'),
 (RTL, 'reset leaves the slot', "drops <= '0; slot <= 1'b0; tokc", "drops <= '0; tokc"),
 (MOD, 'model: the queue is never full', 'full = len(self.fifo) == self.qd', 'full = False'),
 (MOD, 'model: drops are not counted', 'if full: self.drops += 1', 'if full: pass'),
 (MOD, 'model: the slot is ignored', 'bk_in_valid = len(self.fifo) != 0 and not self.slot', 'bk_in_valid = len(self.fifo) != 0'),
 (MOD, 'model: the book is always ready', 'bk_ready = c >= self.busy_until', 'bk_ready = True'),
 (MOD, 'model: the signal is faster', 'self.sig_at[c + self.f + 4]', 'self.sig_at[c + self.f + 3]'),
 (MOD, 'model: a failed event can trade', 'self.r_okres = int(r_ == BG.OK)', 'self.r_okres = 1'),
 (MOD, 'model: the buy threshold is strict', 'if imb >= self.thr: dec = (0,', 'if imb > self.thr: dec = (0,'),
 (MOD, 'model: the ask is the bid', 'if imb >= self.thr: dec = (0, (mid2 + spread) >> 1)', 'if imb >= self.thr: dec = (0, (mid2 - spread) >> 1)'),
 (MOD, 'model: a refusal is not a reject', 'elif self.rej_pend: scy["rep"]', 'elif False: scy["rep"]'),
]
def one(j):
    f, label, old, new = j
    d = tempfile.mkdtemp(prefix="mut26_")
    for sub in ("rtl", "tb", "out", "model", "tools"): shutil.copytree(os.path.join(flow.ROOT, sub), os.path.join(d, sub), ignore=shutil.ignore_patterns("*.json", "*_synth.log", "*.hex", "__pycache__", "ex*_*", "t1[0-9]_*"))
    p = os.path.join(d, f); s = open(p).read()
    if old not in s: shutil.rmtree(d, ignore_errors=True); return label, "BAD ANCHOR (0 occurrences)"
    i = s.index(old); open(p, "w").write(s[:i] + new + s[i + len(old):])
    try: q = subprocess.run([sys.executable, "tools/ch26_run.py", "--battery" if f == RTL else "--battery-model"], cwd=d, capture_output=True, text=True, timeout=900); out = q.stdout.strip().splitlines()[-1] if q.stdout.strip() else "RESULT crash: " + (q.stderr.strip().splitlines() or ["?"])[-1][:70]
    except subprocess.TimeoutExpired: out = "RESULT hang (timeout)"
    shutil.rmtree(d, ignore_errors=True); r = out.replace("RESULT ", "")
    return label, ("NOT CAUGHT" if r == "None" else "caught by: " + r[:110])
if __name__ == "__main__":
    print("NOTE: this script deliberately breaks copies of the RTL and of the model. 'caught' lines are EXPECTED: they show the battery notices the mistake.")
    q1 = subprocess.run([sys.executable, "tools/ch26_run.py", "--battery"], cwd=flow.ROOT, capture_output=True, text=True); q2 = subprocess.run([sys.executable, "tools/ch26_run.py", "--battery-model"], cwd=flow.ROOT, capture_output=True, text=True)
    base = q1.stdout.strip().endswith("None") and q2.stdout.strip().endswith("None"); print("unmutated design and model pass their batteries:", base)
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, MUT))
    cnt = {RTL: [0, 0], MOD: [0, 0]}
    for (f, *_), (label, st) in zip(MUT, res): print(f"  {label}: {st}"); cnt[f][1] += 1; cnt[f][0] += st.startswith("caught")
    for f, (c, n) in cnt.items(): print(f"  {f}: caught {c} of {n}")
    print(f"mutants caught: {sum(c for c, n in cnt.values())} of {len(MUT)}")
