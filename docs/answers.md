# Appendix H. Answers to the Self-Check Questions

Worked answers to the questions at the end of each chapter, and hints for the exercises. Try the question first.

---

## Chapter 1

**1. What is stored in the LUT4 for `y = a AND b AND c AND d`? How many of its 16 bits are 1?**

Worked answer: the output is 1 only when all four inputs are 1, which is the single address `1111`. So exactly one of the 16 bits is 1 (bit 15) and the other fifteen are 0: the table is `0x8000`.

**2. Decompose the 5-input AND into LUT4s.**

Worked answer: two LUTs. The first computes `t = a AND b AND c AND d`; the second computes `y = t AND e` (a function of two inputs, which fits in a LUT4 with two inputs unused). The mapper of Example A would find the same for a 5-input AND, because after splitting on `e` one cofactor is the constant 0.

**3. Why does the `+` adder use fewer LUTs than the gate adder?**

Worked answer: with `+` the tool uses the carry chain, so the LUT of each bit only has to compute the sum bit and the carry logic is in the hard carry cell: about one LUT per bit. In the gate adder the carry is also logic in LUTs, so each bit needs a LUT for the sum and one for the carry (and the generate/propagate terms): about 2.3 LUTs per bit at 64 bits, as measured.

**4. 21.8 MHz: what period, and how many LUT levels?**

Worked answer: 1 / 21.8 MHz is 45.9 ns. If a LUT plus the routing hop to the next costs between one and two nanoseconds on this device, the critical path is somewhere between 25 and 45 LUT levels, which agrees with a ripple through the 64 bits of the adder.

**5. Which Fmax would you quote for the design that gave 39.5 to 46.1 MHz over eight seeds?**

Worked answer: the minimum, or a conservative figure, and the seeds: "39.5 MHz worst of 8 seeds (mean 43.3, maximum 46.1)". A design must work at the clock you choose in every build, and a rebuild with a different seed gives a different placement; quoting only the maximum is quoting the luckiest sample.

**6. Why is the `+` adder identical across seeds on iCE40 but not on ECP5?**

Worked answer: on iCE40 the carry chain forces its cells into one column in a fixed order, so there is little left for placement to vary on the critical path. ECP5's carry cells are also chained, but the registers and the pad connections around them are still placed by the random search, so the result moves by a few per cent (2.6% in the measurement). This is the explanation the data suggests, not something the experiment isolates.

**7. Why is the OR-propagate mutant not counted as a gap?**

Worked answer: for a full adder, `carry = (a AND b) OR (c AND (a XOR b))` and `carry = (a AND b) OR (c AND (a OR b))` are the same function: they differ only when a = b = 1, and then the first term is already 1. No input distinguishes them, so no test can fail, and failing to catch an equivalent mutant says nothing about the tests.

**8. In what sense is an FPGA design's latency deterministic, and what does it rule out?**

Worked answer: a design built as a pipeline of circuits answers a fixed number of clock cycles after its input, every time, because every stage runs in hardware on its own and nothing shares a resource dynamically. It rules out designs where timing depends on the data or on contention: caches, operating-system scheduling, or an arbiter that makes one request wait for another (these exist in FPGA designs too, and a deterministic design avoids or bounds them).

## Chapter 1 -- hints for the exercises

1. The 7-input XOR needs about 3 LUTs by hand (xor of four, then of that and three more); the 8-input AND needs 3. The naive mapper will be further from optimal on the XOR, because its cofactors are the XOR and its complement and are not recognized as the same function.
2. Prefer a variable for which one cofactor is constant or the other cofactor's complement: for AND-like functions this collapses a level.
3. `a - b` is mapped to the carry chain by Yosys on both families; check `SB_CARRY` and `CCU2C` counts.
4. A three-operand add maps to two chained adders unless the family has a ternary adder; compare the carry cells and Fmax.
5. Try mutating the golden vector generator instead of the RTL: for example drop the directed carry patterns and see which mutants survive with random vectors only (the "carry forgets the propagate term" is the usual one).

---

## Chapter 2

**1. Why does `always_comb` with an `if` and no `else` build a latch, and what does `always_comb` do that `always @*` does not?**

Worked answer: when the condition is false the output is not assigned, so it must keep its previous value, and keeping a value needs a memory element: a latch. `always_comb` declares the block to be purely combinational, so a tool can warn (Verilator's `LATCH`) when the body is not; it is also sensitive to everything it reads including inside called functions, it runs once at time zero so its outputs are defined at the start, and it forbids another block from driving the same variable (the `MULTIDRIVEN` warning). A plain `always @*` promises none of that.

**2. Which breaks the stream rule: lowering `valid` next cycle, changing the data next cycle, raising `valid` for a different item after a transfer?**

Worked answer: the first two break it: an offered item (`valid = 1`, `ready = 0`) must stay offered, unchanged, until the cycle in which it is accepted. The third is allowed: after a transfer the item is gone, and the sender may offer the next one.

**3. Why does `vr_slow` move only half an item per cycle?**

Worked answer: its `ready_in` is `!valid_out`. After accepting an item `valid_out` is 1, so `ready_in` is 0 in the next cycle even if the sink takes the item in that cycle; the stage can accept again only when it has become empty. Accept, hand over, accept, hand over: one item per two cycles.

**4. What is the combinational path of `vr_comb`, and how long does it become in a chain of N stages?**

Worked answer: `ready_in = ready_out || !valid_out`, so `ready_in` depends combinationally on `ready_out`. In a chain, the last stage's `ready_out` (the sink) reaches the first stage's `ready_in` through N OR gates in one clock cycle: N LUT levels plus routing, so the delay grows linearly with N, which is why Fmax falls from 316 to 57 MHz over 32 stages on iCE40.

**5. What does the skid register do in the cycle in which the output stalls?**

Worked answer: `ready_in` is a register (`!skid_valid`), so the sender has not yet been told to stop in the first stalled cycle and may offer an item. The stage cannot put it in the output register (which is full and not being emptied), so it parks it in the skid register; `ready_in` then falls in the next cycle. When the output frees, the skid item moves first, so the order is kept.

**6. Why is a skid stage still the right choice for a 32-stage chain?**

Worked answer: a single skid stage costs speed and area because of its data multiplexer (179 against 316 MHz at one stage). But in a long chain the comb version's ready path crosses all the stages in one cycle (57 MHz at 32 stages on iCE40), while every ready of the skid chain comes from a register, so the chain runs at about 135 MHz. The skid buffer pays a fixed cost per stage to remove a cost that grows with the length of the chain.

**7. Why must the SAT proof of equivalence skip the first step and start with a reset?**

Worked answer: before the first reset edge the registers hold arbitrary values; the two machines can be in different (unreachable or at least unaligned) states and their outputs legitimately differ at step 1. Equivalence is a property of the behaviour from a common initial state, which only the reset establishes: so reset is asserted at step 1 (`-set-at 1 in_rst 1`) and the comparison starts from step 2 (`-prove-skip 1`).

**8. Why is 30 cycles meaningful here, and what would make it insufficient?**

Worked answer: the longest frame is 19 bytes (start, length, 16 payload, end), so within 30 cycles every state, every counter value and every abort and recovery path is reachable, and a difference in behaviour would show as a counterexample. It would be insufficient if a difference needed a longer history: a counter that matters only after 100 bytes, a timeout, or a longer frame format. For such designs a bounded proof must be replaced by an inductive one (Chapter 6).

## Chapter 2 -- hints for the exercises

1. Add a parameter for the interval and choose the stage type by `k % INTERVAL == INTERVAL - 1`; the ready path then crosses at most `INTERVAL - 1` comb stages. Sweep the interval at 16 and 32 stages and plot Fmax against LUTs.
2. The parked item must be stored somewhere, so `W` bits per skid stage cannot be avoided; but a two-entry FIFO (two registers with read and write pointers) needs a multiplexer on the *output* only instead of one on each input, which can be cheaper and faster. Try it and compare.
3. `frame_d`: a state register of the enum type, a single `always_ff` with `case (st)`, outputs defaulted at the top of the block, exactly as in `frame_a` but with names. It should come out the same size as `frame_b`.
4. Run the mutation script after removing the case: report the survivors, or report that none survive (then that vector kind was redundant for these mutants, which is also a finding).
5. Candidates: the reset value of an unobserved register (equivalent), or a mutant in code the testbench never drives (a missing test).

