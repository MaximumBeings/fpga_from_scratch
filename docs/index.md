# FPGA from Scratch -- Under Development

![index](assets/art/index.svg)

--8<-- "docs/assets/art/index.md"


An open-toolchain book on FPGA design. It starts from what an FPGA is and builds, step by step, a complete **high-frequency-trading data path** (Ethernet, UDP and TCP, exchange market data, an order book, triggers, pre-trade risk and order entry) as the main running case study; it then applies the same method to case studies in signal processing, radio, security, compression, control, vision, genomics, finance and machine learning.

!!! note "Status"
    The book is **under development**: Chapters 1 to 26 are written; [Contents](contents.md) lists every part and chapter, what each will build, and the tests it will carry. Chapters are added one at a time, each with its code, its recorded output and its mutation run.

## The method (the same as in *Capra: Silicon Compiler from Scratch*)

- an **independent Python golden model** for every circuit;
- **self-checking testbenches in two simulators** (Icarus Verilog and Verilator);
- **every test is tested**: break the design one line at a time and check that the tests notice (mutation testing); equivalent mutants are listed apart from real gaps;
- every number is labelled **measured, derived or assumed**;
- "a model of a design, not a product": no claim goes beyond what the open tools can show.

## What this book is not

It uses **open tools only** (Yosys, nextpnr, Verilator, Icarus Verilog, SymbiYosys). It does not use Vivado, a board, a real 10G PHY or a live exchange feed, so **latency is reported in cycles at a stated clock**, never as measured wire-to-wire nanoseconds, and risk logic is presented as an educational design, not as certified compliance logic.

Companion books: [Capra: Silicon Compiler from Scratch](https://MaximumBeings.github.io/silicon_compiler_from_scratch/) and the OS-from-scratch book.
