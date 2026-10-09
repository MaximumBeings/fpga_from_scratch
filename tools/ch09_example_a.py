#!/usr/bin/env python3
"""Chapter 9, example A: what the header filter costs and how fast it runs. LUTs, flip-flops, block RAMs and Fmax (nextpnr seed 1, asked for 300 MHz) of the FIRST version of hdr_filter (rtl/hdr_v1.sv), the final hdr_filter, and hdr_path (mac_rx + hdr_filter + frame_fifo 2 KB), on iCE40 and ECP5, each behind the pin wrapper that lets it fit a chip; the end points of the critical path of the first and final versions; and where the final filter's LUTs go (one function removed at a time). Usage: ch09_example_a.py"""
import os, re, shutil, sys, tempfile, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import flow, hw
F = ["rtl/crc32_stream.sv", "rtl/mac.sv", "rtl/hdr.sv"]
CASES = [("hdr_filter, first version", "hdr_filter_v1_syn", ["rtl/hdr_v1.sv"], None), ("hdr_filter, final", "hdr_filter_syn", ["rtl/hdr.sv"], None), ("hdr_path (2 KB buffer)", "hdr_path_syn", F, {"AW": 11})]
def job(a):
    k, fam = a; name, top, files, params = CASES[k]; return a, flow.run(files, top, fam, 300, tag=f"hdr9_{top}_{fam}", params=params)
def crit(log):
    i = log.rfind("Critical path report for clock"); j = log.find("Setup", i); sec = log[i:j + 300]
    src = re.findall(r"Source (\S+)", sec); snk = re.findall(r"Sink (\S+)", sec); tl = re.search(r"([\d.]+) ns logic, ([\d.]+) ns routing", sec)
    nm = lambda x: re.sub(r"_(SB_|TRELLIS_|LUT4|CCU2C|PFUMX|L6MUX)\S*", "", re.sub(r"^hf\.", "", x))
    return nm(src[0]), nm(snk[-1]), (tl.group(1), tl.group(2)) if tl else ("?", "?")
ABL = [("per-cause counters (8 x 16 bits)", "else for (int i = 0; i < 8; i++) if (inc[i]) cn[i] <= cn[i] + 16'd1;", ";"),
       ("UDP checksum (pseudo-header + segment)", "f_ucsbad <= (ucs != 16'd0) && !u_sum_ok;", "f_ucsbad <= 1'b0;"),
       ("IP header checksum", "&& ip_sum_ok;", ";"),
       ("VLAN tags", "assign d_vl = (h81 && lo00) || (h88 && loA8);", "assign d_vl = 1'b0;"),
       ("destination-address and port filter", "f_ipbad <= cfg_ip_en && (dip != cfg_ip); f_portbad <= (dport < cfg_plo) || (dport > cfg_phi);", "f_ipbad <= 1'b0; f_portbad <= 1'b0;")]
def lut(src, top, fam):
    d = tempfile.mkdtemp(prefix="abl9_"); os.makedirs(os.path.join(d, "out")); shutil.copytree(os.path.join(flow.ROOT, "rtl"), os.path.join(d, "rtl")); open(os.path.join(d, "rtl", "hdr.sv"), "w").write(src)
    syn = {"ice40": f"synth_ice40 -top {top}; stat", "ecp5": f"synth_ecp5 -top {top}; stat"}[fam]; rc, out = hw._run(["yosys", "-p", f"read_verilog -sv rtl/hdr.sv; {syn}"], cwd=d); shutil.rmtree(d, ignore_errors=True)
    l4 = re.findall(r"\b(?:SB_LUT4|LUT4)\s+(\d+)", out); cc = re.findall(r"\bCCU2C\s+(\d+)", out)
    return (int(l4[-1]) if l4 else 0) + (2 * int(cc[-1]) if (cc and fam == 'ecp5') else 0)
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(4) as ex: res = dict(ex.map(job, [(k, f) for k in range(len(CASES)) for f in ("ice40", "ecp5")]))
    print("== resources and clock (Yosys + nextpnr, seed 1, asked for 300 MHz); 'RAM' = SB_RAM40_4K (iCE40) or DP16KD (ECP5); each design sits behind a pin wrapper (rtl/hdr.sv) that adds 78 configuration flip-flops, a 16-bit output multiplexer and its register")
    print(f"  {'module':26s} | {'iCE40 LUT':>9s} {'FF':>5s} {'RAM':>4s} {'Fmax MHz':>9s} {'Gbit/s':>7s} | {'ECP5 LUT':>8s} {'CCU2C':>5s} {'FF':>5s} {'RAM':>4s} {'Fmax MHz':>9s} {'Gbit/s':>7s}")
    for k, c in enumerate(CASES):
        i, e = res[(k, "ice40")], res[(k, "ecp5")]; ri = i["cells"].get("SB_RAM40_4K", 0); re_ = e["cells"].get("DP16KD", 0)
        print(f"  {c[0]:26s} | {i['luts']:9d} {i['ffs']:5d} {ri:4d} {i['fmax']:9.1f} {i['fmax'] * 8 / 1000:7.2f} | {e['luts']:8d} {e['carry']:5d} {e['ffs']:5d} {re_:4d} {e['fmax']:9.1f} {e['fmax'] * 8 / 1000:7.2f}")
    print("  one byte per clock at 125 MHz is 1 Gbit/s. Gbit/s above = 8 x Fmax (derived), the rate of THIS 8-bit datapath at that clock.")
    print("\n== the end points of the critical path (nextpnr's last report for the clock)")
    for k in (0, 1, 2):
        for fam in ("ice40", "ecp5"):
            s, t, (lg, rt) = crit(res[(k, fam)]["pnr_log"]); print(f"  {CASES[k][0]:26s} {fam:6s} {s:24s} -> {t:28s} {lg} ns logic, {rt} ns routing")
    base = open(os.path.join(flow.ROOT, "rtl", "hdr.sv")).read()
    print("\n== where the logic of the final hdr_filter goes (Yosys synthesis only, no pin wrapper; each row removes ONE function from a copy of the source and reports the logic cells saved; a logic cell = a LUT4 on iCE40, a LUT4 or half of a CCU2C carry cell on ECP5)")
    print(f"  {'removed':44s} | {'iCE40 cells':>11s} {'saved':>6s} | {'ECP5 cells':>10s} {'saved':>6s}")
    b = {fam: lut(base, "hdr_filter", fam) for fam in ("ice40", "ecp5")}; print(f"  {'(nothing: hdr_filter as built)':44s} | {b['ice40']:11d} {'':6s} | {b['ecp5']:10d}")
    for name, old, new in ABL:
        assert base.count(old) == 1, name; v = base.replace(old, new); r = {fam: lut(v, "hdr_filter", fam) for fam in ("ice40", "ecp5")}
        print(f"  {name:44s} | {r['ice40']:11d} {b['ice40'] - r['ice40']:6d} | {r['ecp5']:10d} {b['ecp5'] - r['ecp5']:6d}")
