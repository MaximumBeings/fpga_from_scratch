# Contents

![contents](assets/art/contents.svg)

--8<-- "docs/assets/art/contents.md"


The plan for the whole book. **Part 0 to Part 7 build the trading data path; Parts 8 to 11 are case studies from other domains.** Every chapter carries two running examples, figures, a Python golden model, tests in two simulators, a mutation run and self-check questions with answers (Appendix H). Status: **Chapters 1 to 8 are written** (each marked *written* below); the rest are *planned*.

## Part 1 -- Foundations
1. *(written)* What an FPGA is: LUTs, flip-flops, carry chains, block RAM, DSP slices, clocks, I/O, and the open flow used here
2. *(written)* Hardware design in SystemVerilog: the portable subset (measured), lint as a gate, valid/ready stages and skid buffers, state machines in three styles with a SAT equivalence proof
3. *(written)* Timing: clocks, setup and hold, reset strategy, clock-domain crossing, reading a timing report
4. *(written)* Latency as a budget: pipelines, valid/ready, cut-through against store-and-forward, determinism
5. *(written)* Resources: LUT against DSP against BRAM, fixed-point arithmetic, retiming, what actually costs area
6. *(written)* A verification harness: Verilator drivers, Python golden models, vector replay, constrained random, mutation testing, formal properties

## Part 2 -- Wire to bytes: Ethernet
7. *(written)* Frames and the CRC: parallel CRC-32 at 64 bits per beat
8. *(written)* The MAC datapath: AXI-Stream, FIFOs, clock crossing, the PHY modeled at its interface
9. *(written)* VLAN, IPv4 and UDP at line rate: a byte-serial header filter, the Internet checksum, drop causes (parsing across the beats of a wide datapath is Exercise 2)
10. *(written)* Filtering: exact CAM, ternary CAM, range matcher, hash tables and fingerprints, multicast aliasing (update safety is Exercise 4)
11. *(written)* Egress: UDP frame building, store-and-forward against cut-through, a token-bucket pacer

## Part 3 -- Reliable transport: TCP
12. *(written)* Why orders use TCP: the state machine, segment acceptance, a table of connections, and what must be in hardware
13. *(written)* A TCP send side: window, cumulative ACK, the RFC 6298 retransmit timer, a scanner for many timers
14. *(written)* Testing it against an independent reference stack with loss, reorder, duplication and forged segments injected; run-time safety invariants (a formal proof is an exercise)
15. *(written)* Hot path and cold path: the dispatcher and its order-keeping count, head-of-line blocking, reconnects, the hardware/software split

## Part 4 -- Market data
16. *(written)* Exchange protocols: MoldUDP64 and ITCH, and a generator that turns a message grammar into a parser (SoupBinTCP and OUCH are exercises)
17. Line-rate message parsing: variable-length messages across beats, several messages per packet
18. Sequence gaps and A/B feed arbitration
19. The order book in hardware: per-symbol state, price-level structures (sorted array, CAM, hash in BRAM), top of book
20. Order-book engineering: worst-case latency against depth, checked against a Python golden book

## Part 5 -- Decide and act
21. Triggers: predicates on messages, pipelined comparators, symbol tables
22. Fixed-point signals: imbalance, mid and microprice on DSP and LUT
23. Pre-trade risk: position, notional and rate limits, price bands, kill switch, fail-closed design, formal proof of the invariants
24. Order entry: binary encoding, pre-built templates, session state, sequence numbers
25. Order lifecycle: acks, cancels, replaces, fills, reconciliation

## Part 6 -- The whole system
26. Integration: the wire-to-wire pipeline, a per-stage cycle-budget table, a register interface and DMA to the host
27. Resets, power-up, watchdogs and safe states
28. Timestamps and measurement: defining tick-to-trade, jitter, histograms
29. System tests: replay, scenario generation, fault injection, cycle-count regression

## Part 7 -- Trading case studies and techniques
30. Speculative processing: parse before the checksum clears, with rollback; pre-computed responses
31. Latency against determinism: where jitter comes from, fixed pipelines against dynamic ones
32. Hybrid designs: an FPGA filter in front of a CPU book
33. Many feeds, many venues: arbitration, resource sharing, floorplanning
34. FPGA, ASIC or CPU: a cost model for deciding what belongs in hardware
35. Operations and audit: logging, kill-switch drills, change control (as education, not compliance logic)

## Part 8 -- Case studies: signals and radio
36. A polyphase channelizer and FFT pipeline: streaming fixed-point FFT, an SNR study against a floating-point reference
37. A software-defined-radio receiver: digital downconverter, CORDIC mixer, symbol timing recovery, a Viterbi or LDPC decoder checked against a bit-error-rate curve

## Part 9 -- Case studies: security and data infrastructure
38. A TLS record engine: AES-GCM in hardware, NIST test vectors as golden data
39. SHA-256 and a Merkle-tree offload
40. A compression engine: LZ77 matching and Huffman coding, round-tripped against zlib
41. A regex and deep-packet-inspection engine: regex to DFA in hardware, checked against Python's `re`
42. A key-value store accelerator: a hash table in BRAM with an LSM-style write path

## Part 10 -- Case studies: control and vision
43. A motor-control loop: fixed-point PID, field-oriented control, ADC timing, a plant model co-simulated
44. A computer-vision pipeline: line buffers, convolution, Sobel edges, connected components
45. A real-time 3D transform and rasterizer: barycentric rasterization, a depth buffer, a test image

## Part 11 -- Case studies: science, finance and machine learning
46. A genomics seed-and-extend aligner: a Smith-Waterman systolic array checked against a Python reference
47. A Monte-Carlo option pricer: an LFSR and Box-Muller random source, the variance against the analytic price
48. Neural-network inference: a tiny convolutional network in fixed point, tied back to Capra's quantization chapters
49. Sparse linear algebra: SpMV and a conjugate-gradient solver, with the memory bottleneck analysed

## Appendices
- A. Digital logic recap · B. SystemVerilog reference · C. Ethernet, IP and TCP reference · D. Exchange-protocol reference · E. FPGA families and toolchains · F. Timing-closure playbook · G. Verification cookbook · H. Answers to all self-check questions
- Primers for the case studies: I. DSP · J. Cryptography · K. Error-correcting codes · L. Computer graphics

## How it will be built
In volumes: **Volume 1** is Parts 1 to 4, **Volume 2** is Parts 5 to 7, **Volume 3** is Parts 8 to 11. The chapters of the case-study parts (36 to 49) are independent of each other and can be read in any order after Part 1. Chapters 45 and 46 are marked **optional**: they are far from the trading path and are included to show the method generalizes.
