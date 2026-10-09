// Chapter 6: a Verilator C++ driver for sfifo. Replays out/fifo_vec.hex (the same vector file the SystemVerilog testbench reads) through the compiled model and compares every cycle: the harness a real project uses when simulation speed matters. Usage: sfifo_drv <vector file> <cycles> [repeat]; prints PASS/FAIL and the simulated cycles per second.
#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <vector>
#include "Vsfifo.h"
#include "verilated.h"
struct Line { int wr, rd, data, q, full, empty, count; };
int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc < 3) { std::fprintf(stderr, "usage: %s vectors cycles [repeat]\n", argv[0]); return 2; }
    int n = std::atoi(argv[2]); int rep = argc > 3 ? std::atoi(argv[3]) : 1;
    std::vector<Line> v; FILE* f = std::fopen(argv[1], "r"); if (!f) { std::fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
    char buf[64];
    while ((int)v.size() < n && std::fgets(buf, sizeof buf, f)) {
        Line l; int wr, rd, d, q, fu, em, c;
        std::sscanf(buf, "%1x%1x%2x%2x%1x%1x%1x", &wr, &rd, &d, &q, &fu, &em, &c);
        l = {wr, rd, d, q, fu, em, c}; v.push_back(l);
    }
    std::fclose(f); n = (int)v.size();
    Vsfifo* top = new Vsfifo; long errs = 0, cycles = 0, first = -1;
    auto t0 = std::chrono::steady_clock::now();
    for (int r = 0; r < rep; r++) {
        top->rst = 1; top->wr_en = 0; top->rd_en = 0; top->wr_data = 0;
        for (int i = 0; i < 2; i++) { top->clk = 0; top->eval(); top->clk = 1; top->eval(); }
        top->rst = 0;
        for (int k = 0; k < n; k++) {
            top->clk = 0; top->wr_en = v[k].wr; top->rd_en = v[k].rd; top->wr_data = v[k].data; top->eval();       // inputs applied, outputs settle (before the clock edge)
            bool bad = top->full != v[k].full || top->empty != v[k].empty || top->count != v[k].count || (!v[k].empty && top->rd_data != v[k].q);
            if (bad) { errs++; if (first < 0) first = k; }
            top->clk = 1; top->eval(); cycles++;
        }
    }
    double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    if (errs == 0) std::printf("PASS: %d cycles x %d, %.2f million cycles per second\n", n, rep, cycles / s / 1e6);
    else std::printf("FAIL: %ld mismatches, first at cycle %ld, %.2f million cycles per second\n", errs, first, cycles / s / 1e6);
    delete top; return errs ? 1 : 0;
}
