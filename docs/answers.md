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

## Chapter 3

**1. Write the period equation and say what changes if the clock is 20% faster.**

Worked answer: `T >= t_cq + (LUT + route) x levels + t_setup`. A clock 20% faster has a period 1/1.2 = 0.83 of the old one, so the right-hand side (the sum of delays) must shrink by 17%: fewer levels (with Example A's fit, 1.29 ns per level, a 10 ns path at 100 MHz must drop to 8.3 ns, a bit more than one level fewer), a better placement, or a register cut in the middle (Chapter 4).

**2. The critical path split was 3.1 ns logic and 4.9 ns routing. What would you try first, and why is "use a faster LUT" not on the list?**

Worked answer: routing is the larger part, so first look at *why the wires are long*: reduce fan-out on the nets in the path, register the signals that cross the chip, or pipeline the path; also try other seeds, since the placer's choice moves the routing time. A faster LUT is not a choice: the LUT of the device is what it is, and even a zero-time LUT would remove only 3.1 ns of 8.0.

**3. Why does hold time not depend on the clock period?**

Worked answer: hold concerns the data *changing again after the same edge that captures it*: the launching and capturing edges are the same edge, so the period never enters. A hold violation is a path that is too fast; slowing the clock does not cure it, adding delay to the path does.

**4. Why is the clock you can promise lower than the best seed's Fmax, and how did Example A choose it?**

Worked answer: the best seed is one sample from a spread (111.3 to 124.5 MHz, 11.2%), and the next build, with a different seed or a changed neighbouring design, can land anywhere in it or below it. Example A takes the worst of twelve seeds (111.3 MHz) and 10% below that (100.1 MHz) as the promise. Twelve seeds do not prove a lower bound; they give an estimate.

**5. Why does a reset synchronizer assert asynchronously but release synchronously?**

Worked answer: asserting must work without a clock (the clock may be stopped or not yet running), and an early assert is harmless. Releasing is dangerous if it happens near a clock edge: some flip-flops would see the release in one cycle and some in the next, and the circuit would leave reset half-way. Retiming the release through two flip-flops makes it happen on a clock edge, two edges after the input is released, for every flip-flop at once.

**6. What does the second flip-flop of a synchronizer buy, and what does a third buy?**

Worked answer: each flip-flop gives the signal one more clock period to settle, and the chance of an unresolved value falls exponentially with the time allowed. With the assumed constants of the page, at 200 MHz one flip-flop gives 8 seconds, two give 1.9e4 years and three give 1.3e15 years. A third stage is used when the clock is fast or the consequence of a failure is severe.

**7. A pulse is one 10 ns cycle and the receiving clock has a period of 25 ns. What does the naive circuit deliver, and what does the toggle circuit need?**

Worked answer: the naive circuit delivers only the pulses during which a receiving edge happens to fall (here 80 of 200 in the book's run: about 10/25 = 40% in the long run, as the a register is high for 10 ns of every 25). The toggle circuit delivers all of them, provided successive pulses are far enough apart that no two toggles fall between two receiving edges (at least about three receiving periods).

**8. Why can a multi-bit binary counter not be sent through a bank of synchronizers, and what property of Gray code fixes it?**

Worked answer: each bit is captured independently; when more than one bit changes in a step, a capture in the middle can return a mix of old and new bits, a value the counter never had (for 4 bits, 8 of the 16 steps can do it). In a Gray code exactly one bit changes at each step, so the only possible captures are the old and the new value. The SAT proof shows this for all 16 steps of a 4-bit counter, including the wrap.

**9. Why is `full` computed in the write domain and `empty` in the read domain, and why can each be wrong only in the safe direction?**

Worked answer: each flag decides what *its own side* may do next, so it must be judged in that side's clock, against the other side's pointer arriving through a synchronizer. The pointer a side sees is a little *old*: the writer sees a read pointer that is behind the truth, so it can think the FIFO is fuller than it is (it holds `full` a little too long); the reader sees an old write pointer, so it can think the FIFO is emptier than it is. Neither can think the opposite.

**10. The binary-pointer FIFO passed the data checks but failed the occupancy checks. Give an example of a circuit that would have corrupted data.**

Worked answer: any logic that *acts on the count*: a reader that waits until at least four words are available and then reads four in consecutive cycles without looking at `empty` again; an almost-full flag that releases back-pressure; a DMA that moves `wptr - rptr` words. A count that is too high by a wrapped multi-bit capture sends such a circuit to read words that are not there. (Exercise 2 builds the burst reader.)

**11. Why does the first version of the FIFO (Gray encoder from gates) fail?**

Worked answer: gates between the binary counter and the synchronizer can glitch: in the simulation the encoder output went `0010` -> `0101` -> `0110` within one instant, three bits changing in turn. A capture in the middle of that sees a mix of three bits' old and new values, which is exactly the problem Gray was meant to avoid. The crossing pointer must be a flip-flop output, loaded with the Gray code of the *next* pointer.

**12. Why can no simulation of the ideal synchronizer show that a synchronizer stage is missing?**

Worked answer: without metastability the ideal one-stage and two-stage synchronizers have the same outputs one cycle apart; every functional test passes with both. The model of metastability would show it, but in the book's battery it *replaces* the file being mutated; the check that does catch it is structural (count the flip-flops after synthesis), and a real flow uses a CDC lint tool.

## Chapter 3 -- hints for the exercises

1. A `STAGES` parameter makes `q` the end of a shift register of that length; in the model, only the *first* flip-flop is made metastable, so the extra stages absorb a slowly resolving value only if the model keeps a value in limbo for more than one cycle: you have to extend the model to hold the unresolved value for a random number of cycles. Then find the window at which the number of failures changes between two and three stages.
2. The consumer reads when `rlevel >= 4`, for four consecutive cycles, and a read that the DUT refuses (`empty` high) is counted as an error. Under the metastability model with binary pointers `rlevel` is sometimes too high; with Gray it never is, so the error count is the difference.
3. `flow.run(["rtl/tchain.sv"], "tchain", "ecp5", 200, params={"D": d})`; the intercept and slope will differ because the ECP5 LUTs and routing differ; the *linear* form should still hold.
4. The model gives the delivered count for each gap: loop gap from 1 upwards; the toggle circuit needs the gap times the sending period to exceed one receiving period (41.3 ns here) plus the settling, so a gap of 5 or more (50 ns); confirm in the testbench.
5. A property that bounds the lag: after the writer has been idle for four read-clock edges, `rlevel` must equal the true occupancy. With that property the `rbin_n` mutant is caught (its count is one too low exactly when a read happens), so it ceases to be equivalent: the lesson is that "equivalent" always means "with respect to the properties checked".

## Chapter 4

**1. Define latency, throughput and jitter, and say which of the three a pipeline's structure fixes.**

Worked answer: latency is the number of cycles from an input to the output that depends on it; throughput is the number of inputs accepted per cycle; jitter is the variation of latency from one input to another. A registered pipeline fixes the latency (S + 1 cycles) and the throughput (one per cycle) and so has no jitter; a store-and-forward stage has latency and jitter that depend on the packet.

**2. Why does the book never quote a wire-to-wire time for a design?**

Worked answer: such a time includes the physical interface, the board, cables and the other side's gateway, none of which the simulations or the open tools measure. What can be measured is the number of cycles inside the FPGA and the clock the tools say it can reach; a nanosecond figure from them is labelled as nextpnr's estimate.

**3. The area is 192 LUTs in every row but the flip-flops grow. Why?**

Worked answer: the logic is 12 rounds of one LUT4 per bit (12 x 16 = 192) whatever the cut. Each extra stage adds a register for the 16-bit word and the valid bit (17 flip-flops), so the count rises from 34 to 221.

**4. Fmax rises from 57 to 385 MHz as the stages go from 1 to 12. Why is the rise less than twelvefold?**

Worked answer: each stage still pays clock-to-q, setup and at least one route, whatever the logic in it. With the fit of Chapter 3, those fixed costs (about 0.9 ns plus a route) do not shrink as the logic shrinks, so the period falls by less than the logic does.

**5. Why does the latency in nanoseconds have a minimum rather than falling forever?**

Worked answer: the latency is (S + 1) x period. The period falls toward its floor (the fixed per-stage cost), while the number of cycles keeps growing, so past a point each added stage adds a whole fixed-cost period for a gain that shrinks. In the measurements the latency rises again from about 25 to 29 ns (S = 2 to 6) to 33.8 ns at S = 12.

**6. Why can the data not tell you whether to use 2 or 6 stages?**

Worked answer: the worst-of-six latencies for S = 2 to 6 span 28.3 to 29.2 ns, a range smaller than the seed-to-seed spread of Fmax (up to 20%). A different seed could reorder them; the measurement supports the shape, not the ranking inside the flat part.

**7. Why did the pipeline get an input register, and what did nextpnr report without it?**

Worked answer: a timing tool measures paths from one flip-flop to another. With S = 1 and no input register, the only path is from the input pins to a register, which is not a clock path, and nextpnr reported no maximum frequency at all. The input register makes every logic path register-to-register and costs one cycle (latency S + 1).

**8. What can cut-through decide at the first beat, and what only at the last? How does it handle the second?**

Worked answer: the header test (the low byte of the first beat) is known at the first beat, so a packet that fails it is dropped at once. The checksum depends on every beat, so it is known only at the last; cut-through has already forwarded the packet and raises a `bad` flag on the last beat.

**9. Why must the receiver of a cut-through stream be able to undo work?**

Worked answer: it has already seen the first beats of a packet that turns out to be bad. Whatever it did with them (started processing, updated state, begun a reply) must be abandoned or reversed when the last beat arrives flagged bad.

**10. Why is "40 of 40 streams agree with the specification" a separate check from the testbench passing?**

Worked answer: the testbench compares the RTL with the golden model; if the model were wrong, a wrong design that matched it would pass. The specification is a separate, timing-free statement of what should come out, and the Python check shows that the model, and so the testbench, is judging against the right thing.

**11. Why does a budget for a store-and-forward stage have to be a range?**

Worked answer: its latency is n + 1 cycles for a packet of n beats, so it depends on the packet; with packets of 1 to 12 beats the first-beat latency took eleven values from 3 to 13 cycles. A budget with one number would be wrong for most packets.

**12. One mutant survived the first run of the battery. Which, why, and what closed it?**

Worked answer: the one that does not clear the input valid register on reset. The first testbench held `in_valid` low during reset, so the register was cleared by the idle input anyway and nothing differed. Holding `in_valid` high during reset (a valid input must be discarded by reset) makes the mutant produce a phantom output, and it is caught.

## Chapter 4 -- hints for the exercises

1. Two buffers selected by a toggle bit: one fills while the other drains; `in_ready` goes low only when both are full. The model needs a second buffer and a queue of lengths; for equal lengths n the rate becomes one packet per n cycles. The cost is a second 32 x 32 memory (2 more block RAMs by Example B's measure) and the toggle logic.
2. Throughput is the clock in MHz items per microsecond (one item per cycle). A 30 ns budget at the worst-of-six latency rules out S = 1 (35.1 ns) and S = 12 (33.8 ns) and allows S = 2 to 6 only if their worst-of-six latency is under 30 ns, which Example A says it is (28.3 to 29.2 ns).
3. Add `out_ready` and a hold: either a skid buffer (Chapter 2) at the output, which keeps one cycle of latency and adds registers, or stalling the input, which requires `in_ready`. A stage that can stall no longer has a *single* latency under backpressure: the property becomes "latency 1 when the downstream is ready".
4. `flow.run(["rtl/pipe.sv"], "pipe", "ecp5", 400, params={"S": s})`; compare the Fmax column and the position of the minimum; ECP5's per-stage overhead differs, so the floor can move.
5. Candidates: a reset value of an unobserved register (equivalent), or a mutant in a path the vectors never drive (a missing test): for example, a packet of exactly 32 beats, the buffer depth, which the generators never produce (maximum 12).

## Chapter 5

**1. What does the Q1.15 value `0x4000` mean? What is the product of `0x4000` and `0x4000` in Q2.30 and in Q1.15?**

Worked answer: `0x4000` is 16,384, and 16,384 / 2^15 = 0.5. The product is 16,384 x 16,384 = 268,435,456 = 2^28, which in Q2.30 is 2^28 / 2^30 = 0.25. Narrowed to Q1.15 (shift right by 15) it is 2^13 = 8,192 = `0x2000`, which is 0.25. Exact, because 0.25 is representable.

**2. Why is the accumulator 40 bits for 16 x 16 products? How many products can it hold at full scale?**

Worked answer: a product is 32 bits (Q2.30). Each doubling of the number of terms needs one more integer bit; 8 extra bits hold 2^8 = 256 products at full scale without overflow. The largest magnitude of a product of two Q1.15 numbers is 2^30 (-1 x -1 = 1), 256 of them sum to 2^38, which fits in 40 signed bits.

**3. Why is truncation biased in two's complement, and by how much on average?**

Worked answer: dropping low bits is a floor: it rounds toward minus infinity for positive and negative numbers alike, so the error is always zero or negative, from 0 to just under one step. If the dropped bits are uniformly distributed the average error is half a step: the measured mean is -0.499 least-significant bits.

**4. Rounding 2,047 to 6 bits with a shift of 4 gives 128. Why does the circuit carry an extra bit, and what does saturation do with it?**

Worked answer: 2,047 + 8 = 2,055 and 2,055 >> 4 = 128, which does not fit in a 6-bit signed value (maximum 31). The extra bit stops the addition of the rounding constant from overflowing the *input* width before the shift. Saturation sees 128 > 31 and returns 31; wrap would keep the low 6 bits of 128 and return 0.

**5. Why can `fx_round_sat` be tested on every input and a 16 x 16 multiplier not?**

Worked answer: the number of inputs is 2^(input bits): 4,096 to 16,384 for the narrowing circuits at the widths tested, but 2^32 pairs for a 16 x 16 multiplier (and 2^40 inputs for the 40-bit narrowing). Exhaustive testing is for the small instances; the large ones are tested on random and corner-heavy traffic against a model.

**6. Why does a 16 x 16 multiplier in logic cost four to five times an 8 x 8, and what happens beyond 18 bits in a DSP block?**

Worked answer: a W x W multiplier has W rows of W partial-product bits, so the logic grows with W squared: doubling the width gives about four times the LUTs (measured: 4.2 on iCE40, 5.4 on ECP5). The DSP block multiplies 18 x 18 bits; a wider operand is built from several blocks and extra adders: four blocks at 24 and 32 bits, with a lower Fmax (88 MHz at 24 bits against 144 at 16).

**7. Why are the ECP5 and iCE40 LUT counts for the same multiplier not comparable?**

Worked answer: the two flows map the multiplier with different rules and different carry structures (the ECP5 carry cell holds logic that iCE40 counts as LUTs), so the totals measure the tools and devices together, not the multiplier. Compare a family with itself.

**8. Why can a block RAM not implement an asynchronous read? What did that cost in the 16-word memory?**

Worked answer: a block RAM's read port is clocked: the data appears after an edge. An asynchronous read needs the data in the same cycle as the address, which only an array of flip-flops with multiplexers (or LUT RAM) can provide. The 16 x 16 memory cost 256 flip-flops and 197 LUTs on iCE40, against about 22 LUTs and one block RAM for the synchronous version.

**9. What does `n/a` mean in the Fmax column, and why must the 976 MHz entry not be read as a design clock?**

Worked answer: `n/a` means the design has no register-to-register path, so there is nothing for the timing tool to measure (an asynchronous read goes from input pins to output pins). 976 MHz is a memory with an output register measured alone: the path is nearly empty, and any real design is limited by its other logic and the clock network.

**10. The two FIR forms have the same outputs. Why is the transposed one faster, and what does it spend to be so?**

Worked answer: in the direct form the whole sum of eight products is formed in one clock period (a multiplier then an eight-input adder tree). In the transposed form each period holds one multiplier and one adder, with a register between adders. It spends registers (300 flip-flops against 150), which are cheap in an FPGA, to remove a long combinational path, which is expensive.

**11. Why is rounding once at full width 16 times more accurate than rounding each product?**

Worked answer: each rounding adds an independent error of up to half a step; the errors of 256 roundings add as a random walk, so the standard deviation grows with the square root of the count (about 16 times that of a single rounding). Adding at full width and rounding once introduces a single rounding error whatever the number of terms: measured standard deviation 0.289 against 4.609.

**12. The first direct-form FIR had latency 3. Which test caught it, and why would a test of the frequency response alone not have?**

Worked answer: the cycle-by-cycle comparison with the model, on the first compared cycle. A frequency response would show the same magnitude at any delay, so a pure delay is invisible to it; only a test that pins the *latency* sees a change of one cycle.

## Chapter 5 -- hints for the exercises

1. Round to nearest even: add half, but if the dropped bits were exactly one half *and* the result's low bit would be 1, clear it. Extend `round_sat` with a `mode` and test exhaustively as before. The bias of ties-to-even is zero for any input distribution; round-half-up is biased only on ties, which are rare for random products.
2. A symmetric filter needs only 4 multipliers: add `x[k-i] + x[k-(7-i)]` first (one extra bit of width) and multiply the sum by `C[i]`. Whether Yosys reports fewer DSP blocks depends on how it handles the pre-adder width (17 bits still fits an 18 x 18 block).
3. Expect long placement; run with a timeout and report if it times out, or reduce the width first. 4,096 flip-flops fit in 7,680 logic cells, but the 256-way multiplexers add LUTs.
4. `nextpnr-ice40 ... --seed 1` prints the critical path; look for the block RAM clock-to-out and the route to the output register.
5. Candidates: a reset value of an unobserved register (equivalent), or a mutant in code the vectors never drive (a missing test): for example, a memory whose vectors never read the address being written would let a write-first mutant survive (the vectors here make a fifth of the reads do so, which is what catches it).

## Chapter 6

**1. Why is the golden model written independently of the RTL, and what would be lost if the testbench computed its own expected values from the RTL's signals?**

Worked answer: a model written from the specification can disagree with the design; one derived from the design's own signals agrees with it by construction, including when the design is wrong. The independence is what makes a mismatch informative.

**2. What does `rd_data` get compared against when the FIFO is empty, and why?**

Worked answer: nothing: the comparison is skipped when `empty` is 1. The specification only defines `rd_data` when a word is present; comparing it when empty would flag differences the specification allows (the memory's old contents).

**3. Why does a vector file make the Icarus and Verilator runs comparable?**

Worked answer: both read the same inputs and the same expected outputs, so any difference in result is a difference in the simulator or the driver, not in the stimulus. It also lets the stimulus be generated, inspected and replayed outside any simulator.

**4. The driver reports 15.7 million cycles per second and the whole process 2.4 million. What accounts for the difference, and which number would you quote?**

Worked answer: the driver's own figure times only the simulation loop; the process time also includes starting, and reading and parsing a million text lines. Quote both and say what each includes: the first is the simulator's speed, the second what a user waits for with a file-driven flow.

**5. Which two injected bugs did the directed test miss, and what would you add to it to catch them?**

Worked answer: bug 4 (a read and a write in the same cycle when empty) and bug 6 (a write of `0xA5` when five words are held). Add a cycle with both enables set on an empty FIFO, and a write of `0xA5` at five words (and, generally, writes of a few special values at every occupancy).

**6. Constrained random found bug 6 about eighteen times faster than uniform random but was no better on bugs 1 to 5. Why?**

Worked answer: bug 6 needs a particular data value at a particular occupancy; the constrained generator draws half its data from a list that contains `0xA5`, raising that chance from 1/256 to about 1/12 per write. Bugs 1 to 5 depend only on occupancy and enables, which uniform random already visits quickly in a six-deep FIFO, so the bias adds nothing.

**7. Constrained random with 200 cycles covered fewer bins than uniform random with 200. Why?**

Worked answer: its phases are 20 to 80 cycles long and biased; a phase that holds the FIFO near empty for most of 200 cycles never reaches occupancy 5 or 6. Uniform random wanders over all occupancies. The bias pays only when the run is long enough to visit several phases.

**8. What does bounded model checking prove, and what does it say about cycle 21 when run to depth 20?**

Worked answer: that no input sequence of up to 20 cycles from reset violates the property. It says nothing about cycle 21 or later: a violation needing 21 cycles would not be found.

**9. The counting properties were proved by induction yet bug 3 passes them. Why, and what property catches it?**

Worked answer: bug 3 (a late-wrapping write pointer) writes words to the wrong place but leaves the count correct, and the counting properties talk only about the count and the flags. The tagged-word property (the k-th word read equals the k-th word written) mentions the data, and the bounded run of it finds the bug.

**10. What is a SAT miter, and why must it be tested on a design compared with itself and on a deliberately different design?**

Worked answer: a circuit built from two designs with the same inputs that outputs 1 when any pair of outputs differs; the solver is asked whether it can ever be 1. A checker that reports "different" for a design compared with itself, or "equal" for a changed design, is broken; the first version of this one did the former because of a tool detail, and only the known-answer test showed it.

**11. 29 of 30 generated mutants died to the 44-cycle directed test. Does that mean the directed test is good? What does the injected-bug table say?**

Worked answer: it means the directed test is good at killing the mutants these operators produce, which are easy. The injected-bug table shows it misses two of six realistic bugs (a missing combination and a data-dependent corner). A mutation score is evidence about the tests *relative to the mutants*; it must be read with a set of realistic bugs.

**12. Why was a survivor "proved equivalent for 14 cycles" and not simply "equivalent"?**

Worked answer: the miter is a bounded search; it shows no difference within 14 cycles from reset. A difference that needs a longer sequence would not be found. (Here the guard is redundant because the write is already blocked when full, which is an argument for equivalence at any length, but the tool's evidence has the bound.)

## Chapter 6 -- hints for the exercises

1. Add the bug as `BUG == 7` with a pair of counters (writes wrapped, and the coincidence); a coverage bin "two wraps then read+write at three words" is the new `coverage()` entry; random testing will need many thousand cycles, formal will need a deeper bound (probably 30+ cycles and minutes); report the numbers you measure.
2. Port `constrained()` (a few lines) and the deque model (an array and two indices) to C++; the speed will be limited by the simulator, not the file.
3. The tagged-word property needs invariants relating the pointers, the count and the position of the tagged word (for example, "if the tag is stored, it is at index `(rp + (k - nr)) mod DEPTH` and `count > k - nr`"); without something like that induction fails for lack of reachable-state information.
4. An operator such as "replace `&& !empty` with `&& (!empty || wr_en)`" produces bug 4's behaviour: a read accepted when a write is simultaneous. Count how many generated mutants the new operator adds and whether the directed test kills them.
5. Add `(1, 1, x)` on an empty FIFO and `(1, 0, 0xA5)` at five words to `directed()`; the directed test then finds all six; coverage rises to 15 or 16 bins (the 3-cycle full and empty runs need more cycles).
