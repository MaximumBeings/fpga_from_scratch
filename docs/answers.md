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
