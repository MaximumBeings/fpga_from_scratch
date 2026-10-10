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

## Chapter 7

**1. Which four conventions define the Ethernet CRC-32 on the wire, and what happens to the result if any one is wrong?**

Worked answer: bits are processed least-significant first (the reflected polynomial `0xEDB88320`), the register starts at all ones, the result is inverted, and it is sent low byte first. Get any one wrong and the value differs from every other implementation's, so a frame sent by one end fails the check at the other, though the design may look self-consistent in a closed test.

**2. What is the residue, and why does a receiver not compare the CRC with the FCS field?**

Worked answer: running the CRC over a frame followed by its own FCS always leaves `0x2144DF1C`. The receiver runs the CRC over every byte it received, FCS included, and tests for that one constant: no separate comparison, no need to find the FCS field when the frame length is not yet known.

**3. Why is the CRC register update linear over GF(2), and what does that make possible?**

Worked answer: each step shifts and XORs the register with a constant that is selected by one bit; with addition as XOR the new register bits are XORs of old register bits and data bits, and after N bits the same is true with larger sets. Linearity lets N steps be written as one XOR network, lets the state part and the data part be computed separately (pipelining), and gives the basis-vector proof.

**4. How does the generator find the XOR equations without doing any algebra by hand?**

Worked answer: it runs the bit-serial algorithm with each register bit held as a set of variables (an integer bit mask): the shift moves the sets, the conditional XOR replaces a set with the symmetric difference. After the N steps the sets are the equations.

**5. Why can only the last beat of a frame be partial, and what does the design do for it?**

Worked answer: a stream of bytes is cut into beats of W/8 bytes, so every beat is full except possibly the last. The generator emits one update function per byte count (1 to 8) and the design selects by `in_nbytes`; the pipelined design moves that selection out of the feedback loop.

**6. What do `A_k` and `B_k` stand for, and why does separating them allow pipelining?**

Worked answer: `A_k` is the 32 x 32 matrix applied to the old register, `B_k` the matrix applied to the k data bytes, and new state = `A_k(state) ^ B_k(data)`. `B` depends only on the input, so it can be computed in as many stages as wanted; only `A_8` and one XOR remain in the loop through the state register, and that loop is what limits the clock.

**7. Why was the SAT proof of the 64-bit update abandoned, and what replaced it? What does the proof need to assume?**

Worked answer: the miter has 96 free input bits and long XOR chains, which SAT solvers handle badly (no result in 100 seconds even for two bytes). It was replaced by a basis proof: the circuits are affine (only XOR and NOT gates after mapping) and give zero for zero input, hence linear, and a linear function that matches on the 96 unit inputs matches everywhere. It assumes that the mapped netlist really is what the RTL describes (the gate-type check is on the mapped netlist of the same source).

**8. XOR and NOT gates only: why is that "affine", and why does the all-zero test make it linear?**

Worked answer: XOR gates preserve linearity; a NOT is XOR with the constant 1, so a network of XORs and NOTs is a linear function plus a constant. If the all-zero input gives zero, the constant is zero.

**9. Why do idle cycles carry random junk in the stimulus? Which mutant needed it?**

Worked answer: the interface says the data, byte count and last signals are don't-cares when `valid` is low, so a correct design must ignore them. With zeros on idle cycles a design that forgot to gate its update on `valid` still held its state (a byte count of zero is a no-op), and the mutant that removed the `in_valid` gate survived until the idle cycles carried junk.

**10. Writing the same XOR as a tree instead of a chain doubled the clock. Why did the tool not do it?**

Worked answer: the technology mapper used here optimises area first and keeps the structure it is given for XORs: a left-to-right chain of 34 inputs became a chain of LUTs (11 levels on the critical path), while an explicit tree of 4-input groups needs 3. A delay-driven script might restructure it; the open flow's default did not.

**11. 54 corruptions were missed with a 16-bit check and none with 32 bits. What does the ratio say, and what would you need to see a 32-bit miss?**

Worked answer: a random corruption passes an n-bit check with probability about 2^-n: 4,000,000 / 65,536 = 61 expected, 54 seen. At 32 bits the expectation is 4,000,000 / 2^32 = 0.001, so seeing one would take about four billion corruptions.

**12. The pipelined design reaches 7.9 Gbit/s on ECP5. What limits it now and what would you do about it?**

Worked answer: the critical path is the last stage: the choice of one of eight `A_k` matrices applied to the snapshot and the XOR with `B_k` (about five LUT levels, not in a loop). Cut it into two registered stages (for example, compute all eight `A_k` products' needed parts first, or split the multiplexer from the XOR); the loop stays at three levels, and the clock should rise towards the 156.25 MHz a 64-bit 10GbE datapath needs.

## Chapter 7 -- hints for the exercises

1. Register the output of the eight-way `A_k` selection (`ak`) in one stage and do the XOR with `B_k` and the comparison in the next; the path is then a 20-input XOR with a mux in front (about four levels). Measure on ECP5; the loop remains at 3 levels, so a result near 150 MHz is plausible but not guaranteed.
2. The FCS is the registered final `~st` after the last data byte; if the last beat has k bytes (k < W/8) the FCS bytes fit in the same beat when k + 4 <= W/8, otherwise a second beat is needed. Test both cases for every k.
3. `W = 128` means 16 bytes per beat: the generator's `d` input becomes 128 bits and the functions go up to `step16`; the row weights grow to about 80; expect a lower clock and many more LUTs.
4. The Hamming distance of this CRC at short lengths is large (every 3-bit error was detected in the 12-byte frame); the search for undetected 4-, 5- and 6-bit patterns is a sampling problem: undetected patterns are rare, so use the linearity (an error is undetected iff the CRC of the error pattern alone, with zero initial value and no final inversion, is zero).
5. Candidates: a mutant in code that the interface rule makes unreachable (equivalent), or a frame length the stimulus never produces (the stimulus covers 1 to 200 bytes randomly and 1 to 80 exhaustively, so a 1,500-byte frame would be the missing test).

## Chapter 8

**1. What is the inter-frame gap and why does the transmitter count 12 cycles of idle?**

Worked answer: the gap is the minimum idle time of 96 bit times between frames, which is 12 byte times on a byte interface. It gives the receiving end time to finish a frame and be ready for the next. The transmitter loads 11 after the FCS and counts down so that the next preamble starts no earlier than 12 cycles after the last FCS byte; the test measured a minimum gap of 12 at all three source speeds.

**2. How does `mac_rx` find the start of a frame, and what does it do with a run that does not fit the pattern?**

Worked answer: inside a `dv` run it needs at least one `0x55` followed by `0xD5`. Anything else (no preamble byte, no SFD, a run that ends first) sends it to the ignore state until `dv` falls, so nothing is reported for that run.

**3. Why does the receiver hold each data byte for one cycle?**

Worked answer: the FCS is the last four bytes and the receiver cannot know a byte is among them until the frame ends. A four-byte delay line lets it release a byte only when four more have arrived, so the FCS never leaves; the one-cycle hold gives the last released byte its `last` mark in the same cycle the frame ends.

**4. Why compare the CRC register with `0xDEBB20E3` and not with `0x2144DF1C`?**

Worked answer: the register is not inverted at the end. `0x2144DF1C` is the residue after the final inversion; the un-inverted register holds its complement, `0xDEBB20E3`. Comparing the wrong constant makes every good frame look bad.

**5. Why does a receive MAC output have no `ready`, and what is the consequence for the buffer behind it?**

Worked answer: the PHY cannot be paused; bytes arrive at a fixed rate. The buffer behind must accept every byte, so it must hold the largest frame it will commit, and when it cannot it must drop a whole frame and count it.

**6. What does the frame buffer do with a bad frame, and why is it better than dropping the bad frame at the output?**

Worked answer: the write pointer rolls back to the commit pointer, so the bad frame's bytes never become visible and take no space for later. Dropping at the output would hold the space until the frame reached the reader and would need the reader to know the verdict.

**7. Why is the commit pointer shown to the reader one cycle late, and why can the MAC never trigger the problem?**

Worked answer: with a synchronous-read memory the data is available a cycle after the address; showing the new commit pointer at once would let the reader see an entry whose data has not yet been read out. The mutant that removes the delay only fails when a frame of one or two bytes is read right after commit; the MAC's frames are at least 60 bytes, so only the unit test with short frames exposed it.

**8. What does the loss guard add, and what property does it give?**

Worked answer: when the crossing FIFO is full the guard remembers that the frame lost a byte, drops the rest, and forces a terminator with the bad flag, so the downstream buffer rolls the frame back. The property: loss costs whole frames and never corrupts one.

**9. Derive the condition (a) for a core clock too slow for a crossing FIFO of depth D.**

Worked answer: in a frame of N bytes the PHY writes N bytes in N·Tphy while the core reads N bytes in N·Tcore. The pile-up is N·(1 − Tphy/Tcore) bytes, and it must stay below D. With N = 1518, D = 16 and Tphy = 8000 ps, Tcore may exceed Tphy by about 1%; the measured edge, with synchronizer latency, lay between 8050 and 8100 ps.

**10. Why is condition (b) independent of the depth, and why does it matter in the 64-byte case?**

Worked answer: (b) compares average rates over many frames: if the core is slower than the PHY, any finite buffer eventually overflows however deep it is. It matters with back-to-back minimum frames because the within-frame pile-up is tiny there, so (a) never trips, but (b) still sets a limit.

**11. Why must the transmit buffer hold the largest frame? What happens if it does not?**

Worked answer: the transmitter must not start a frame it cannot finish, and it has no way to pause the wire. The buffer holds the whole frame before the transmitter starts; if it cannot, the frame is dropped whole (the overflow counter), and a frame that started and ran dry would be an underrun, which the sticky flag reports.

**12. Name two survivors of the first mutation run and the test that closed each.**

Worked answer: (i) start accepted with no preamble byte, closed by a frame kind with a junk byte before the SFD; (ii) minimum length 63, closed by frames of exactly the boundary lengths. Others: the frame-buffer pointer mutants, closed by the unit test with frames of 1 byte to twice the buffer; the loss-guard mutants, closed by the 40-pair recovery test.

## Chapter 8 -- hints for the exercises

1. Register the full flag (computed from the next write pointer) and the incremented read/write pointers one stage ahead; the added latency is a cycle and a few flip-flops. Re-run the unit test with frames of 1 byte to twice the buffer to check nothing else changed.
2. Sweep the core period in steps of 10 ps for each depth with a single 60-byte frame; the difference between the nominal depth and the measured one in bytes, times the byte period, divided by the core period, gives the number of cycles to compare with the two-flop synchronizers on each pointer.
3. When the PHY clock is faster, the transmit side underruns: the asynchronous FIFO empties mid-frame. The cure is to start only when the whole frame is present (the commit pointer crosses as a Gray code) or to run the core at least as fast as the PHY.
4. A PAUSE frame is an ordinary good frame with a fixed destination address and type; the receiver needs those 14 bytes before the verdict, so decode in the receive path, not the byte stage; the transmitter stops when its counter, in units of 512 bit times, is non-zero.
5. Candidates: a mutant in the unreachable top bit of the saturating byte counter (equivalent), or a frame of exactly 1,522 bytes passing through the transmit side (a boundary the transmit tests do not use).

## Chapter 9

**1. Why does the Internet checksum add with an end-around carry, and why is the byte order of the words irrelevant to the check?**

Worked answer: adding 16-bit words modulo 65,535 (ones' complement) means a carry out of bit 15 is worth 1 at bit 0, which is why it is added back. The operation is commutative and associative, so words may be added in any order, and swapping the two bytes of every word swaps the bytes of the sum, which the receiver compares in the same order. That is why the byte lanes of the lane accumulator can be summed separately and combined at the end.

**2. How does a receiver check an IPv4 header without computing the complement of the sum?**

Worked answer: the sender stores the complement of the sum of all the other words, so the sum of all the words including the checksum field is `0xFFFF` (all ones). The receiver sums the header and compares with `0xFFFF`. With the carry deferred into bit 16 the test is two comparisons: `low = 0xFFFF` with no carry or `low = 0xFFFE` with a carry.

**3. What is the UDP pseudo-header, and what does it protect against?**

Worked answer: the source address, the destination address, a zero byte with the protocol (17) and the UDP length, added to the checksum but never sent. It ties the datagram to the addresses it travels between, so a datagram delivered to the wrong host, or with corrupted addresses, fails the check even if the UDP segment itself arrived intact.

**4. What does a UDP checksum field of zero mean, and what does a sender send when the sum comes out as zero?**

Worked answer: zero means the sender computed no checksum, and the receiver must not verify it. A sender whose computed checksum is zero sends `0xFFFF` instead (the same value in ones' complement), so that zero stays reserved for "none". The model's `csum_zero` frames exercise exactly that, and the filter forwards them.

**5. Why does the filter need the IPv4 total length and the UDP length, when the frame already ends?**

Worked answer: Ethernet pads a short frame with zeros to 60 bytes and a sender may add a trailer, so the end of the frame is not the end of the datagram. The total length says where the IP packet ends (and must not exceed what arrived); the UDP length says which bytes the UDP checksum covers. Without them the checksum would include the padding or the trailer. The `trailer` frames (random bytes after the datagram) are forwarded only because the segment is summed up to its length.

**6. What value does the pair (`low`, `carry`) represent in the deferred-carry accumulator, and when is the sum correct?**

Worked answer: the value `low + carry` modulo `0xFFFF`: the carry still has to be added back. The sum is correct (equals `0xFFFF`) when `low = 0xFFFF` and `carry = 0`, or `low = 0xFFFE` and `carry = 1`. The case `low = 0xFFFF` with `carry = 1` is the value 1 after folding, not `0xFFFF`.

**7. Why are the positions in the headers one-hot shift registers, and what do they cost?**

Worked answer: a field is captured by `if (position bit) field <= byte`: the position is already decoded, so the capture is one LUT, with no counter and no decoder in front of it. The cost is flip-flops, 20 for the IP header and 8 for the UDP header, and a shift of the whole register every byte. Flip-flops are cheap in an FPGA (each logic cell has one) and the saving is in the critical path.

**8. Why are the control registers cleared by the last byte of a frame and the data fields by the first byte of the next?**

Worked answer: the control state must be at its initial value when the first byte of the next frame arrives, so the last byte restarts it (through the flip-flops' synchronous reset, which costs no LUT). The data fields and sums, on the other hand, are still needed for the verdict in the cycle after the last byte, so they are cleared only when the next frame begins (its first byte is an Ethernet byte and captures none of them). The state the frame ended in is copied (`st_v`, `ntags_v`) for the verdict.

**9. Why is the verdict in two stages, what does it cost and what does it not cost?**

Worked answer: the first stage turns the registers into single-bit facts, each at most one 16-bit comparison deep; the second combines them by priority. One long expression was the critical path of the first version. It costs one more cycle of latency (3, measured) and about 140 flip-flops for the delayed copies of the fields; it does not cost throughput, because each stage holds a different frame and the next frame's first byte may arrive in the very next cycle.

**10. Name two survivors of the first mutation run, one that was a missing test and one that was code that cannot matter.**

Worked answer: a missing test: the version check accepting 5 as well as 4 survived because no frame had version 5; it died when the wrong-version frames drew from the near misses. Code that cannot matter: the second fold in `csum_def`'s final sum: the first fold's value is at most `0x1FF00`, so the second never carries; the right action was to delete it.

**11. Why do the three accumulators rank differently on iCE40 and ECP5?**

Worked answer: ECP5 has dedicated carry chains that make a second 16-bit adder cheap, so folding the carry in the same cycle costs little (148.8 MHz against 157.7 with the carry deferred); iCE40's carry chain is slower, so the two adders in a row run 21% slower than the deferred form (130.8 against 166.5 MHz). The lane version has no 16-bit word to form, and is the fastest on both (182.0 and 229.7 MHz) at the price of about 40% more LUTs on iCE40.

**12. Why does `hdr_path` run slower than `hdr_filter`, and where is its critical path?**

Worked answer: it contains Chapter 8's `frame_fifo`, whose pointer arithmetic (the full test and the increment in front of the memory address) and block-RAM output are slower than the filter: 88.4 MHz on iCE40 and 117.9 on ECP5 against 122.4 and 155.6. The critical paths named by the tool are `hp.ff.wptr -> n_bad` on iCE40 and `hp.ff.rptr -> the RAM output` on ECP5, both inside the frame buffer.

## Chapter 9 -- hints for the exercises

1. The address words and the UDP length are added at fixed positions, so a second accumulator needs only two sources and the segment accumulator only two (`{hold, byte}` and the odd last byte): one LUT level in front of each adder. The verdict then needs `A + B` to fold to `0xFFFF`, which for two folded 16-bit sums holds when `B` is the bitwise complement of `A`, except when both are `0xFFFF`. Fold each one first (add the carry); that adds an incrementer to the first stage of the verdict, so check that it does not become the new critical path.
2. With no tag the IP header starts at byte 14 (inside beat 1, lane 6), with one tag at byte 18 (beat 2, lane 2), with two at byte 22 (beat 2, lane 6). The source address is at IP bytes 12 to 15, so at frame bytes 26 to 29, 30 to 33 or 34 to 37: the third case straddles beats 4 and 5. Write a function in the model that returns (beat, lane) for each field byte and each tag count, then design the capture as a small table indexed by the tag count.
3. The option type is the first byte of the options (IP byte 20), and each option has a length byte, except the two single-byte options (end of list `0x00` and no operation `0x01`); the state machine must walk the options to find the types, which needs a counter and a remembered "refuse" flag. The stimulus needs both types, both as the first and as a later option, with options before the source route, and a frame with a `0x83` byte inside the data of another option (which must not be taken for an option).
4. The update is `HC' = ~(~HC + ~m + m')` in ones' complement, where `m` and `m'` are the old and new 16-bit words containing the TTL. Run all 65,536 old checksums against every TTL and compare with the full recomputation of the header; the boundary to look at is where the sum folds to `0x0000` or `0xFFFF`.
5. Candidates: a mutant in the saturation of the byte counter (`ipc[11]`), which no frame of up to 1,522 bytes reaches (equivalent for the stimulus, a limit of the design), or in the `uact` guard of the segment counter (equivalent, the counter is reloaded before it is used).

## Chapter 10

**1. What is the difference between a CAM and a RAM, and what does a CAM cost per entry in an FPGA?**

Worked answer: a RAM is addressed by position and returns the content; a CAM is addressed by content and returns the position or value of the entry that equals (or matches) the key, by comparing the key with every entry at once. In an FPGA that means a comparator and registers per entry: 34 to 54 LUTs and about 35 flip-flops per slot for a 32-bit exact CAM (twice the flip-flops for a ternary one), measured.

**2. What does a 1 bit and a 0 bit in a TCAM mask mean, and does the stored key have to be zero where the mask is zero?**

Worked answer: a 1 means the key bit must equal the stored bit; a 0 means "don't care". The stored key need not be zero where the mask is zero: the compare is `((key ^ q) & mask) == 0`, which ignores those bits. The stimulus stores random key bits there to make sure of it.

**3. Two ternary entries match a key. Which one wins, and what must the control plane do to get longest-prefix matching?**

Worked answer: the lowest slot, not the most specific. For longest-prefix matching the control plane sorts the prefixes so that longer prefixes occupy lower slots (Exercise 1).

**4. Why is a range needing two comparators per entry cheaper on ECP5 than on iCE40?**

Worked answer: measured, the range matcher takes 2,178 LUTs at 64 slots on ECP5 against 2,465 on iCE40, and 34 LUTs per slot against 46 for the exact CAM on the same chip, using 1,040 carry cells. The likely reason is that a magnitude comparison maps onto ECP5's carry cells, which cost no LUTs of their own; the chapter did not isolate the cause (an experiment would synthesise the comparator with and without carry cells).

**5. Why does the clock of a CAM fall as the number of entries grows?**

Worked answer: the key fans out to N comparators, and the priority encoder is a chain over N match bits; both grow with N, and nothing is pipelined beyond the one register between them. Measured: 137, 78 and 38 MHz at 16, 32 and 64 exact slots on iCE40.

**6. How does a query see exactly the writes of earlier cycles in the CAM, whose value is read a cycle after the compare?**

Worked answer: a write takes effect at the end of its cycle. The compare of a query in cycle t sees the slots as they are in t, so it misses a write of cycle t (as required) and sees one of t - 1. The value read in cycle t + 1 happens before the end of t + 1, so a write in t + 1 cannot change it. The testbench interleaves writes, deletes and queries to show it.

**7. What does two-choice hashing do to the share of keys that cannot be placed, and why does it cost a second RAM read?**

Worked answer: a key that finds its first slot taken has a second chance, so the share falls (21.1% against 35.3% at 95% load with the same 512 slots, 6.2% against 21.3% at 50%). A lookup does not know which slot holds the key, so it reads both and compares.

**8. Derive the share of keys that cannot be placed in a table of `m` slots with `n` random keys.**

Worked answer: a given slot stays empty with probability `(1 - 1/m)^n`, so the expected number of occupied slots is `m(1 - (1 - 1/m)^n)`; each occupied slot holds one key, so the rest of the `n` keys, `n - m(1 - (1 - 1/m)^n)`, did not find a place. Divided by `n` it is 11.4% at n = 128 and m = 512, which the model measures as 11.5%.

**9. Why were consecutive keys placed perfectly by one table, and `stride` keys badly by two?**

Worked answer: the fold XORs the key's chunks, so consecutive keys have consecutive low chunks and fall into different buckets: better than random. In two tables of 256, 486 keys at 95% load overflow table 0 (256 slots), and the overflowing `stride` keys go through the second hash, which maps them badly (it has rank 6): 34.2% fail against 21.1% for random keys.

**10. What is a rank, and why does the rank of the second hash change the false-positive rate of a fingerprint?**

Worked answer: the hash is linear over GF(2), so the number of output bits that the high key bits control is the rank of the matrix. If two keys agree in the low `KW` bits, their hash difference is a function of the other bits only, and it is zero with probability 2^-rank. Hash 2 has rank 6 instead of 8, so such keys collide in table 1 four times as often as an independent hash would, and the table-1 term of the false-positive rate is four times larger: 1.16e-2 against the uncorrected 5.4e-3, with the measured 1.15e-2.

**11. Why does a filter on a multicast MAC address accept frames to groups the node has not joined, and what must be done about it?**

Worked answer: the MAC address of a group keeps 23 of the group's 28 variable bits, so 32 groups share an address. A filter on the MAC address accepts all 32 when it accepts one (300 of 300 alias frames in the test). The frame must be checked again at the IP level, with the full group address.

**12. Name two survivors of the mutation runs and the test that closed each, and say which one was a simulator blind spot.**

Worked answer: a deleted slot that still matched (exact CAM) survived because the deleting write left a random key in the slot; closed by deletes that keep the old key and queries for the keys of deleted entries. A reset that did not clear the valid bits survived because Icarus starts registers at `x`, and `if (x)` is false, so the CAM looked empty anyway (and Verilator starts at 0): the blind spot; closed by powering the registers up with garbage in the testbench.

## Chapter 10 -- hints for the exercises

1. Sort by prefix length, longest first; two prefixes of equal length cannot both match a key, so their order is free. The default route goes last. The model: for each address, among all prefixes that contain it, take the longest. Insert and delete with a stable order (shift entries) and test with random inserts and deletes interleaved with lookups.
2. A standard bound: try up to 500 moves; each move writes one slot, so one insertion at high load may cost several writes (the model counts them). Use a visited set to detect a loop. Compare with the "not placed" rates of Example B at the same loads: for two tables the placement threshold rises sharply (above 90%).
3. Take the second hash as the fold of `k ^ (k >> 11) ^ (k << 7)`, check the rank with `rank()` for `KW` from 8 to 24, and repeat the measurement. A multiplication costs about one adder per set bit of the constant when built from LUTs; choose a constant with few set bits.
4. Two tables A and B: queries read the table named by a `sel` bit; software writes the other one; flipping `sel` takes effect in the cycle after the write of `sel`, and the query pipeline has two stages, so a query issued in the cycle of the flip uses the new table and one issued before it the old one; the model needs the sel bit to be part of the query's tag.
5. Candidates: a mutant in the unused high bits of `w_addr` (equivalent: only the low bits index the array), or a mutant that stores a wrong value in a slot that is never queried (a missing test only if some run queries every slot).

## Chapter 11

**1. Why can a transmitter not simply send a UDP frame's bytes in order as the payload arrives?**

Worked answer: the IP total length, the UDP length and both checksums stand in the headers, before the payload, and the UDP checksum depends on every payload byte. The transmitter must know the whole payload before the first header byte that depends on it can leave: so it buffers the payload (store-and-forward), or it is told the length in advance and gives up the payload checksum (cut-through).

**2. What does a UDP checksum of zero mean in IPv4, and what must a sender do when its sum comes out as zero?**

Worked answer: zero means "no checksum was computed", and the receiver does not check. A sender whose computed checksum is zero sends `0xFFFF` (the same value in ones' complement). The model builds payloads whose checksum is zero (`csz` packets) and 38 of 200 frames in the filter test carry `0xFFFF`.

**3. What fields go into the UDP checksum that are not in the UDP header?**

Worked answer: the pseudo-header: the source and destination IP addresses, a zero byte with the protocol (17), and the UDP length (which is in the UDP header but is counted twice: once in the pseudo-header and once with the header). Mutants that dropped each of those words were caught.

**4. What does cut-through give up, and what does it demand from the source?**

Worked answer: it gives up the UDP payload checksum (the field is 0) and the ability to drop a bad frame before it starts. It demands a descriptor with the length first and a source that supplies the payload without a gap: a stall inside a payload makes `mac_tx` underrun (8 of 8 runs at 90% and at 60% source speed).

**5. Derive the cycles per packet and the link utilisation of the store-and-forward builder for a payload of `L` bytes.**

Worked answer: the measured cycles per packet are `2 L + 65` (265, 1,065, 2,065 and 3,009 at 100, 500, 1,000 and 1,472 bytes), the wire cost being `L + 66`: the wire idles for `L - 1` cycles per packet. The utilisation is `(L + 66) / (2 L + 65)`: 51.6% at 1,000 bytes. The `65` is a fit, not derived from the state machine: ingest `L`, about 11 cycles of checksum arithmetic and the request, the wire time `L + 54`, with the last 16 cycles of the frame's tail (FCS and gap) overlapping the next ingest.

**6. Why does the cut-through builder keep the wire 100% busy although its checksum takes 11 cycles?**

Worked answer: stage A takes the next descriptor and computes its IP checksum while the previous frame is on the wire; stage B starts the next frame in the cycle `mac_tx` is ready. The arithmetic is hidden behind the transmission of the previous frame, so the cycles per packet equal the wire cost at every length (84, 166, 566, 1,066 and 1,538).

**7. What is a token bucket, and what is guaranteed about the traffic it grants?**

Worked answer: a credit that rises at a constant rate up to a bucket size, from which each frame takes its cost. In any interval of `T` cycles the grants add up to at most the bucket plus `rate x T`: the shaping guarantee, which the test checks for every pair of frames of every run (the slack was never negative and reached 0.1 bytes).

**8. Derive the spacing of frames and the number of frames in a burst for a pacer with rate `r` (in 1/256 byte per cycle) and bucket `B`.**

Worked answer: in the long run each frame of cost `c` needs `c x 256` units of credit, gained at `r` per cycle: the spacing is `256 c / r` cycles (1,066 x 256 / 32 = 8,528). In a burst each frame takes `c` and the credit regains `c x r/256` during the frame's own wire time, so it falls by `c (1 - r/256)` per frame; the `k`-th frame leaves back to back while `B - (k - 1) c (1 - r/256) >= c`: `k <= 1 + (B - c) / (c (1 - r/256))`: 2, 4, 8 and 17 frames for buckets of 2, 4, 8 and 16 KB at `r = 32` (measured the same).

**9. Why did the first pacer limit the clock, and which three changes made the second faster?**

Worked answer: the grant was one combinational expression: a 24-bit comparison, a subtraction, an addition and a saturation, feeding the builder's state machine: 59.6 MHz on iCE40. The second registers the cost and the credit change, registers the comparison and the delayed request (the grant becomes three flip-flops and a gate), and selects the next credit between two sums computed in parallel; with a power-of-two bucket the saturation is a single-bit test. 76.5 MHz, at the price of three cycles of latency.

**10. Why must the bucket be at least the largest frame's cost?**

Worked answer: a frame is granted only when the credit covers its whole cost, and the credit never exceeds the bucket: a bucket below 1,538 bytes (the cost of a 1,472-byte payload) would never grant that frame.

**11. Name one mutant that was code that cannot matter and one that was outside the interface's contract.**

Worked answer: code that cannot matter: the separate overflow flag of the store-and-forward builder (the test at the last byte already drops every oversize payload), or the saturation of the credit on a grant (the credit cannot rise). Outside the contract: the cut-through builder taking its last-byte marker from the source's `s_last` (the interface says it matches the descriptor's length).

**12. What is the critical path of the whole transmit system, and why is it not the pacer?**

Worked answer: the builder's output byte (the header/payload selection, driven by the byte counter or read from the RAM) goes combinationally into the CRC register of `mac_tx`: for cut-through `k` to the CRC on both chips, for store-and-forward the RAM output to the CRC on ECP5. The final pacer's grant is three flip-flops and a gate, so its paths are short; it still costs 9% of the clock for store-and-forward on iCE40, which this chapter did not trace.

## Chapter 11 -- hints for the exercises

1. A one-entry register at the builder output is not enough because `ready` can drop before the first byte only; but once a frame has started `mac_tx` never stalls, so a plain output register (valid, data, last) works if the builder's state machine runs one cycle ahead and the first byte is held until `o_ready`. Latency grows by one cycle; check that the underrun flag stays zero in the cut-through tests.
2. Two banks: the ingest writes bank A while the output reads bank B; the utilisation limit becomes the wire (100%) when the ingest of the next payload is at most as long as the wire time of the previous, which holds for `L + 54 >= L`. New cases: both banks full while a third payload arrives (the source must see `s_ready` low), and an oversize payload in the middle (the drop must not disturb the frame being sent).
3. The checksum is over bytes that have not been seen yet, so a cut-through transmitter cannot compute it; the options are to let the producer compute it (offload), to keep the payload in a buffer (store-and-forward), or to send a template whose checksum is correct for fixed payload and update it incrementally for the fields that change: `HC' = ~(~HC + ~m + m')` (RFC 1624).
4. A policer takes the same credit but drops a request that is not covered: the model is the same bucket with `go = covered` and the request consumed either way; the test sends a stream above the contracted rate and checks that the accepted bytes over any interval stay within bucket + rate x T and that the drop counter plus the accepted frames equal the offered frames.
5. Candidates: a mutant in the unused high bits of `p_len` (equivalent: the cost never exceeds 1,538), or in the `A_IDLE` handling of a descriptor with `d_len` of zero (outside the interface's contract: a payload of zero bytes cannot be offered).

## Chapter 12

**1. Why are sequence-number comparisons modular, and how does `a < b` work in hardware on 32 bits?**

Worked answer: sequence numbers wrap from `2^32 - 1` to 0, so "before" cannot be an ordinary comparison. `a < b` is true when the top bit of `a - b` (computed modulo `2^32`) is set: the difference is negative as a signed number. That is right as long as the two are less than `2^31` apart. Membership of a window is `(x - lo) mod 2^32 < w`. The tests use bases near the wrap (`0xFFFFFFF0`) and in the middle (`0x7FFFFFF0`), and every comparison was exact.

**2. State the acceptability test for a segment and say what an unacceptable segment draws.**

Worked answer: with the segment length `L` = data + SYN + FIN: if `L = 0`, acceptable when `RCV.NXT <= seq < RCV.NXT + wnd` (just `seq = RCV.NXT` if `wnd = 0`); if `L > 0`, never when `wnd = 0`, otherwise when the first byte or the last byte (`seq + L - 1`) lies in the window. An unacceptable segment draws an ACK (`SEQ = SND.NXT, ACK = RCV.NXT`) and is dropped, unless it carries a RST, which is dropped silently.

**3. Why does a RST in the window but not at `RCV.NXT` draw a challenge ACK, and what attack does the rule stop?**

Worked answer: an attacker who cannot see the connection can only guess sequence numbers; if any number in the window reset the connection, a guess would succeed with probability `wnd / 2^32` per packet (large for a big window). Requiring exactly `RCV.NXT` makes it `1 / 2^32`; the challenge ACK lets a legitimate peer that really reset answer with the exact number. The same reasoning applies to a SYN in the window.

**4. What are `SND.UNA`, `SND.NXT` and `RCV.NXT`, and how does each change on a SYN, a FIN, data and an ACK?**

Worked answer: `SND.UNA` is the oldest unacknowledged sequence number, `SND.NXT` the next one we will send, `RCV.NXT` the next we expect. A SYN or a FIN occupies one sequence number: sending one advances `SND.NXT` by one; receiving one advances `RCV.NXT` by one. Data in order advances `RCV.NXT` by its length (limited to the window). A valid ACK in `(SND.UNA, SND.NXT]` sets `SND.UNA` to it.

**5. Why did the window test find that a segment longer than the window is refused at the offsets between its first and last byte?**

Worked answer: the rule accepts a segment when its first byte or its last byte lies in the window. A segment that starts before the window and ends after it (it covers the window and more: length greater than the window plus one) has neither byte inside, so the rule refuses it, although it overlaps the window completely. The test showed it for `wnd = 1`, `ln = 5`: only offsets -4 (last byte at 0) and 0 (first byte at 0) are accepted. A real stack trims the segment to the window before the test; this model does not.

**6. Why does the first design run at 33 MHz, and what are the two parts into which the second cuts it?**

Worked answer: one cycle holds the RAM read, several 32-bit subtractions, comparisons, the priority of the rules and the multiplexers of the answer: a path of 11 ns of logic and 19 ns of routing on iCE40 (one connection). The second design cuts it into the arithmetic (all differences, sums and equalities, in parallel from registered values) and the choice (flags and one-bit predicates in, state and segment out), and then the comparisons from the arithmetic: 3 and 4 stages, 59.9 and 66.1 MHz on iCE40.

**7. What does the bypass of `tcp_tab` do, and what happens to the throughput of one connection without it?**

Worked answer: the RAM is read in the cycle in which the previous event's result is written; for the same connection the read returns the old state. The bypass register holds the new state and replaces the read. Without it (`tcp_tab2`) the event must wait: one event per 3 cycles (three stages) or 4 (four stages) for one connection, instead of one per cycle.

**8. How many cycles apart can events for the same connection be accepted in `tcp_tab2`, and why?**

Worked answer: 3 (three stages) or 4 (four stages): the next event's RAM read must come after the previous event's write, which happens at the end of the last stage. `ev_ready` is low while the connection id of the presented event is in any stage; measured 3.00 and 4.00 cycles per event for one connection, 1.04 and 1.08 for events spread over 64 connections.

**9. Why does the table's size barely change the LUTs, and what does it change?**

Worked answer: the logic is one machine whatever the number of connections; the state is in memory. 16 to 1,024 connections cost 2,760 to 2,782 LUTs on iCE40, and the block RAM grows from 7 to 26 blocks (103,424 bits). It changes the kind of memory: on ECP5, 16 connections fit in distributed RAM (92.5 MHz, no block RAM), larger tables use block RAM and run at 68 to 72 MHz.

**10. List what the hot path tests, and say what is "punted".**

Worked answer: the state is ESTABLISHED; the flags are exactly ACK; the sequence number equals `RCV.NXT`; the length is at most the window; the ACK is in `[SND.UNA, SND.NXT]`. Everything else (the handshake and the close, a RST, a SYN, a FIN, an old or out-of-order segment, a bad ACK, every other state) is punted to the full machine or to software.

**11. Derive the share of events the hot path cannot handle from the rate of oddities and the fixed cost of a connection.**

Worked answer: if a connection has `n` steady-state segments, a fraction `p` of them odd, and about 10 events of handshake and close, the cold events are `10 + p n` of `n + 10`. With `n = 2,000` and `p = 3%` that is 70 / 2,010 = 3.5%; the measured share (3.3% cold) is close; at `p = 30%` the derivation gives 30.3% against 30.7% measured. For short connections the fixed cost dominates.

**12. Name two mutants of the mutation run that were missing tests, and the test that closed each.**

Worked answer: the hot path that does not advance `SND.UNA` survived because no test had data outstanding in ESTABLISHED (the model sends no data, so `SND.UNA` equals the ACK); the uniformly random states with data outstanding closed it. The other kind: a crash of the test script on an `x` in the output; the parser now treats an `x` as a failure.

## Chapter 12 -- hints for the exercises

1. Register the RAM output (`mem_q`) in its own stage before the arithmetic, which removes the RAM's clock-to-output delay from the 8.7 ns path; split `tcp_sel` into the state decision (which flags and predicates select) and the construction of the segment fields. Expect latency 5 to 6 and one event per 5 to 6 cycles for one connection; across connections one per cycle.
2. A bypass from the write data back to the arithmetic stage's state input removes the wait but puts the whole choice in series with the arithmetic for that case (the longest path again); alternatively detect the same-connection case and recompute only the fields that changed. Measure Fmax with and without.
3. The rule: if `seq < RCV.NXT`, drop the first `RCV.NXT - seq` bytes; if the end is beyond the window, drop the tail and ignore the FIN. The acceptable offsets then become `-(ln-1) .. wnd-1` for the data (still refused if the whole segment lies before `RCV.NXT`); the delivered length is the part inside the window.
4. Ignoring a RST in TIME_WAIT (RFC 1337) changes the model's transition, the section 6 test is unchanged, and the mutants for "RST in TIME_WAIT closes" must be rewritten; it protects against a stray RST from an old connection terminating TIME_WAIT early and letting old segments be accepted by a new connection.
5. Candidates: a mutant in the unreachable `default` of the event decoder (equivalent), or in the saturation of `ack_fut` for states in which `SND.NXT - SND.UNA` is 2^31 or more (outside the model's contract: the model assumes less than half the sequence space is outstanding).

## Chapter 13

1. `SND.UNA` is the oldest byte not yet acknowledged, `SND.NXT` the next byte to send, `SND.MAX` the highest `SND.NXT` ever reached. After a timeout `SND.NXT` goes back to `SND.UNA` (go-back-N); `SND.MAX` remembers how far the first transmission went, so that a segment below it is flagged as a retransmission and an ACK beyond it is refused.
2. The length is the least of the bytes available (`end - SND.NXT`), the peer's window left (`SND.UNA + wnd - SND.NXT`, zero if negative) and the MSS. A segment is a retransmission if its first byte is below `SND.MAX`.
3. Karn's rule: take no round-trip sample from an ACK for a segment that was retransmitted. The ACK cannot be matched to the first or to the second transmission, so the measured time may be too long or too short; the timer cancels the sample at a timeout and a retransmission never starts one.
4. First sample `R = 100`: `SRTT = 100`, `RTTVAR = 50`, `RTO = 100 + 4 x 50 = 300` (`srtt8 = 800`, `rv4 = 200`). Second sample `R = 140`: `err = 40`, `RTTVAR = 3/4 x 50 + 1/4 x 40 = 47.5`, `SRTT = 100 + 40/8 = 105`, `RTO = 105 + 190 = 295`. In fixed point `srtt8 = 840`, `rv4 = 200 + 40 - 50 = 190`, `RTO = 105 + 190 = 295`.
5. With `srtt8 = 8 SRTT` the update `SRTT += err/8` is `srtt8 += err`, an exact integer add; with `rv4 = 4 RTTVAR` the factor 3/4 is `rv4 - (rv4 >> 2)`. Only the shift truncates, by less than one unit of 1/4 tick, and the truncation is inside a decaying term (it pulls toward a fixed point), so errors do not accumulate: the run in Example B stays within 4 ticks of the floating-point RFC.
6. The segment at `SND.UNA` is retransmitted (at most one MSS, and never more than what is outstanding), `SND.NXT` goes back to it, the RTO doubles (clamped to the maximum), the timer restarts and the pending sample is cancelled. The retransmission is flagged, starts no sample and its ACK is not sampled.
7. When new data is acknowledged without a sample (everything was retransmitted), RFC 6298 leaves the doubled RTO in place; with no later sample it would stay at its maximum forever. The model recomputes the RTO from `SRTT` and `RTTVAR`. The first version of the model, without it, stayed at `RTO_MAX` after the first loss burst and the 20% runs did not finish in a sensible time.
8. One connection's timer is a comparator; a table of 1,024 would need 1,024 comparators. The scanner visits one connection per cycle, injecting a TICK when no outside event uses the cycle. A timer is checked once every N cycles, so its lateness is between 0 and N - 1 cycles (measured: 1, 3, 15, 63 for N = 2, 4, 16, 64), more when outside events take cycles.
9. Ten 32-bit adds, subtracts and compares chain: `R`, `err`, `|err|`, `rv4`, the sum, the clamp, the deadline. Cut it into three stages (sample, estimator and clamp, deadline), register in between, and use the 16-bit-narrow comparisons of the RTO clamp where the range allows.
10. After a loss everything from `SND.UNA` is sent again, including segments the receiver already holds; under 20% loss 4,623 segments were retransmitted for 200 segments of data. Fast retransmit resends only the lost segment after three duplicate ACKs, without waiting for the timer; SACK tells the sender what the receiver has, so that only the holes are resent.
11. A real network can reorder; the chapter's in-order receiver (a model of a minimal one, no out-of-order buffer) drops any segment that is not exactly the next, so a reordering channel turns jitter into extra loss and the lossless run did not finish. The FIFO channel isolates the sender's behaviour from the receiver's.
12. None was a missing test. Four were the clock-granularity term `max(G, 4 RTTVAR)`, unreachable because `rv4 >= 2` whenever a sample exists, so the term was removed from the RTL; one (the time stamp `now1 <= now`) was equivalent to the original, since `now0` is `now`. The mutation run then caught 51 of 51 (52 of 52 after Chapter 14's correction added a mutant).

## Chapter 13 -- hints for the exercises

1. Three stages (sample and error, estimator and clamp, deadline); the connection record then has a pipeline hazard of two cycles for one connection, which the bypass register must cover. Measure the two numbers: Fmax and the extra latency in cycles of the result.
2. A wheel enters a connection at the slot of its deadline, so lateness is bounded by the slot width (8 ticks) instead of N cycles; the cost is a RAM of linked slots (a connection must be removed when its timer restarts) and a rule for deadlines further away than 256 x 8 ticks.
3. The model needs a duplicate-ACK count, reset by new data; at three, emit the segment at `SND.UNA` flagged as a retransmission without changing `SND.NXT` or the timer. Expect far fewer retransmitted segments at 1% to 5% loss and a smaller gain at 20%.
4. With window 0 and data waiting, the present sender sends nothing and starts no timer, so a lost window update deadlocks it; the closed loop with a variable window (`wnd_var`) and loss finds it as a run that never completes.
5. Candidates: a mutant in the unused high bits of `SND.MAX` arithmetic (equivalent), or in the clamp of a window larger than 2^16 (outside the contract); decide which by writing the stimulus that would tell them apart.

## Chapter 14

1. If the oracle is the model, a test finds only disagreements between the RTL and its own specification, never an error in the specification. Chapters 12 and 13 had that test. An independent reference tests the specification: where two designs written separately agree on what the user sees, a shared misreading of the RFC is far less likely (though not impossible: both were written by the same author).
2. (a) The reference receiver keeps early segments and the DUT drops them: it shows what the DUT's simplification costs and that the DUT stays correct anyway. (b) The reference sender uses a fixed timeout and fast retransmit, the DUT an RFC 6298 estimator and go-back-N: the DUT receiver sees different arrival patterns (single resends, not runs). (c) The reference client does the handshake and the close and retransmits its own SYN and FIN, which the DUT cannot: it exposes the missing control-segment timer. Each difference moves the test off the DUT's own habits.
3. A counter incremented where the channel decides to duplicate or delay would go on counting if a mutation made the channel ignore the decision. The counters (`duped`, `late`, `lost`) are derived from what the receiver can observe: copies actually queued, segments that arrived after a later one, segments that never joined the queue. Three mutants of the channel are caught by exactly this.
4. For example: `SND.UNA <= SND.NXT <= SND.MAX <= end` (caught the bug of Finding 1 and "avail counts from SND.UNA"); the retransmission flag equals "starts below the old SND.MAX" (a retransmission never flagged); an ACK beyond `SND.MAX` never accepted (the forged ACKs); the timer runs exactly while data is outstanding (a timer that is not stopped when everything is acknowledged); `SND.UNA` never decreases (an old ACK accepted as new); new data stays inside the window.
5. An exact RST at `RCV.NXT` legitimately closes the connection, and data at `RCV.NXT` is indistinguishable from the real next segment: the receiver would be right to accept either, so the test would fail the design for being correct. The forged segments are the ones a correct design must ignore.
6. It stays in `SYN_RCVD`: the DUT has no timer for the SYN-ACK. The client's SYN, retransmitted, is answered with a plain ACK (the SYN's sequence number is one below `RCV.NXT`, so it is unacceptable and gets an ACK), which a client in `SYN_SENT` ignores because it has no SYN with it. The shim re-sends the SYN-ACK; in hardware the timer of Chapter 13 would.
7. A reordered segment is dropped by the DUT receiver, so the sender must send it again, and learns that only from a timeout (no fast retransmit): about one RTO and a go-back-N resend per reordered segment. The reference receiver keeps it and sends one ACK when the hole fills; the sender never sees a gap. Both senders are the same design; the receiver decides.
8. A segment cut short by the window (say 40 bytes) is in flight: `SND.MAX = SND.UNA + 40`. The timeout retransmitted `min(MSS, end - SND.UNA) = 100` bytes and set `SND.NXT = SND.UNA + 100`, above `SND.MAX`; 60 of the bytes had never been sent. The receiver accepted them and acknowledged `SND.UNA + 100`, which the sender refused as "beyond `SND.MAX`", so it never advanced. Earlier tests never had less than a segment in flight at a timeout (their windows were large or their traces had no timeout in that state).
9. At 99 bytes every timeout retransmits 100 bytes; the receiver keeps 99 and acknowledges them; `SND.NXT` is `SND.UNA + 100`, one byte past `RCV.NXT`, so the next segment is out of order and dropped, and only the next timeout repairs it, with the RTO doubled in between. At 100 bytes the segment fits and nothing is ever retransmitted: 572 ticks.
10. A data-integrity check cannot see a transfer that finishes slowly. The budget caught nine mutants the byte comparison and the invariants did not: in the reference client, fast retransmit at the first duplicate ACK, no fast retransmit, ignoring the window, the timeout not reset by an ACK, the peer's FIN not acknowledged and the FIN's sequence number off by one (the harness's control shim completes the close, but late); in the sender, a new ACK that does not restart the timer, a timeout that does not cancel the sample, and a timeout that does not go back.
11. A mutant is equivalent when no input distinguishes it. For each of the nine a scenario exists that does (the hand-checked scenarios added in this chapter: a retransmission starting no sample, an ACK below the timed number taking none, the deadline to the tick, the clamp, a duplicate ACK's window, the retransmission of what is outstanding, an unacceptable segment acknowledged and not processed, a second FIN at `RCV.NXT`, an overlapping segment). They are missing tests.
12. The pairings reach 16 of the 203 (state, event class, next state) combinations and 6 of 11 states, because the peers are well behaved: they never send a RST to a closed port, never open actively against the DUT, never send nonsense in the handshake. End-to-end evidence says the common path works under stress and finds situations nobody thought of (Finding 1); fuzz and directed lives say every rule is right. Use both, and use the first as the source of new directed tests, as this chapter did.

## Chapter 14 -- hints for the exercises

1. In `tx_next` the timeout length becomes `min(MSS, SND.MAX - SND.UNA, wnd)` (only when `wnd` is nonzero; with zero window send nothing and keep the timer). Then `SND.NXT = SND.UNA + n` stays at or below `SND.MAX`. Rerun Example B: the one-byte misalignment disappears, so 99 and 60 bytes should cost a handful of timeouts, not one per segment; check that section 2 and Chapter 13's tests are unchanged except the numbers that depend on partial segments.
2. Give each connection a second deadline for its last control segment and let the scanner issue a TICK for it as for data (a connection in `SYN_RCVD` or `LAST_ACK` has no data timer running, so one timer register can serve both). The test is section 3 without the shim.
3. `RCV.NXT + k*MSS` bitmap of arrived segments (the segment boundaries are the sender's: record offsets, not bytes) and the payloads in a RAM; on the segment at `RCV.NXT`, deliver it and then the run of recorded ones. Mutation-test the new logic; Example A is the benchmark.
4. For `tx_next`, the transition relation is combinational from the state and the event: state the invariant, assume it before the event, assert it after. Without the guard on `SND.MAX` in the timeout the old code violates the invariant in one step from a state with `SND.MAX - SND.UNA < MSS` and more data written; that is the counterexample the proof should print.
5. Candidates: a mutant of the reference's fast-retransmit threshold from 3 to 4 (equivalent for the budget at these loss rates; a test would need a profile with a particular duplicate-ACK run), or one in the unreachable `default` of the event decoder (equivalent).

## Chapter 15

1. Hot: a segment for a connection with nothing pending that `tcp_fast` accepts (ESTABLISHED, plain ACK, `seq = RCV.NXT`, length within the window, ACK number within `[SND.UNA, SND.NXT]`). Punted: every application command, every other segment, and every event of a connection that has events pending.
2. If it were taken on the hot path it would be processed before the earlier, pending event, which software has not finished: the connection's events would be handled out of order (a FIN before the data that precedes it, say), and the state software writes back later would overwrite the hot path's update. The count of pending events is what prevents both.
3. `first` says that nothing was pending when the event was punted, so the hardware's state is current and software must load the snapshot (the hot path may have moved `RCV.NXT` since software last saw the connection). Always 0: software works from a stale state after a hot period and the model's transparency check fails. Always 1: software reloads the snapshot for events that arrive while earlier ones are pending, which loses the state it has computed and not yet written back.
4. It decrements the count, which is what lets the connection return to the hot path. (The count cannot be decremented at the pop: software has not finished.) If a push for the same connection arrives in the same cycle, the count goes down by one and up by one.
5. Transparency: the segments sent, the bytes delivered and the final state are those of the single state machine fed the same events in the same order, for any timing of software. It is the specification of a split (the split must not be visible), it needs no knowledge of the design's internals, and it is independent of the timing, so it can be checked over many random timings.
6. An exception keeps its connection pending for about `L` cycles (one pop and one write-back). In that time `phi = (connection's event rate) x L` more events of the connection are expected; each is punted and keeps the connection pending for another `L` cycles, in which `phi` more are expected, and so on: `phi + phi^2 + ... = phi / (1 - phi)`.
7. The derivation assumes software is idle when an event arrives, so that each pending period is exactly `L`. At phi = 0.5 the dragged-in events themselves saturate software (22.9% of the traffic punted, mean wait 1,503 cycles), the pending periods stretch, more events are dragged in, and the measured 10.5 events per exception is ten times the derived 1.0.
8. With POLICY 0 the event at the head of the input waits for room in the FIFO; every event behind it waits too, whichever connection it belongs to. Room appears once per `L` cycles, so a burst of `B` exceptional events with a FIFO of `D` entries blocks the input for about `(B - D) x L` cycles (375 against 384 derived for `B = 32`, `D = 8`, `L = 16`).
9. When the peer's retransmission is cheap and software is fast enough that drops are rare; it keeps the hot events moving (the longest wait of another event was 5 cycles) but dropped 22 of 32 and 112 of 128 burst events at a depth of 8, and most of the traffic when software is slow.
10. In ESTABLISHED the machine of Chapter 12 sends no data, so `SND.UNA = SND.NXT` and an acceptable ACK number equals the value already stored: the store is invisible to every test, and the mutation run said so. A sender (Chapter 13) has data in flight, so the hot path must store the ACK number, and the tests must have data in flight to notice if it does not.
11. In hardware it is two events (the open command and the SYN-ACK) and a write-back; the time is software's: about `L` cycles for each punted event plus its wait in the FIFO. Measured, from the arrival of the SYN-ACK to the write-back leaving the connection ESTABLISHED: 5.2, 18.8 and 84.2 cycles on average for `L` = 4, 16 and 64.
12. (a) The hot path's store into `SND.UNA` and the table update's `consumed` condition: code that cannot matter (`SND.UNA = SND.NXT` in ESTABLISHED; a hot event is always consumed), so the RTL was simplified. (b) Software popping an empty FIFO: a missing test, closed by spurious pops in the closed loop. (Also: the ACK's sequence number from `SND.UNA` instead of `SND.NXT`, equivalent for the same reason, and the passive flag in the snapshot, redundant for transparency.)

## Chapter 15 -- hints for the exercises

1. The count and the snapshot are unchanged; add `SND.NXT`/`SND.MAX` writes on send (a second source of table updates in the same cycle as events: priority and bypass), and the hot update `t_una <= ack`. Extend `with_decoys`/the stimulus with `E_WRITE`-like events from the application that advance `SND.NXT`. The test that fails first when the store is missing is the one with an ACK number above `SND.UNA` and data outstanding, which the present stimulus never produces.
2. A RAM read takes a cycle, so read the entry for the next event while the current one is being decided and forward the write (hot update or write-back) when the connection is the same; the write-back arrives from outside at any time, so it needs its own bypass. Keep `count` per connection in registers so that the decision does not wait for the RAM.
3. Safe only if the event is processed by software to the same effect as by nothing: a duplicate segment that merely produces an ACK and changes no state. Then software cannot be overtaken in a way that matters; the hot path still must not take an event *after* a state-changing event is pending, so the rule is "raise the count only for events that may change state". The model's `reference_check` is the test.
4. Two FIFOs and an arbiter that always serves the setup FIFO first; `first` and the count work unchanged, since ordering per connection is by the count. Measure the other events' extra wait and the reconnect latency at `L = 64`; expect the latter near `L` plus the setup queue.
5. Candidates: a mutant in the unreachable `default` of the event decode, or one that changes the count width (wider than any queue can fill: equivalent).

## Chapter 16

1. Session (10 bytes), sequence number of the first message (8), count of blocks (2), then the blocks, each a 2-byte length and a message. Count 0 is a heartbeat (no blocks); 0xFFFF marks the end of the session, and the parser does not compare it with the number of blocks.
2. The type and length of a block are known at the start, but the error class (unknown type, wrong length) and the complete fields are known only at the end; the registers are stable on the last byte, and the next block's two length bytes give the output time to be read before anything is overwritten.
3. One shift register `f_<name>` of the field's width and one select `s_<name>` that is an OR of `(ty == type && off >= start && off < start + width)` terms, one per type; the register shifts in the byte, big-endian, whenever the select is true.
4. The type byte is itself at body offset 0; the type register holds it only from the next byte on, and the error class likewise. Fields start at offset 1 or later (after the type), so by then the registered values are valid.
5. If the generator and the model both read the grammar, a wrong layout in it would be in both and nothing would disagree. With the model's own `struct` layouts a typo in one copy fails a test. A misreading of the protocol that is the same in both copies still passes, and the layouts here are from memory.
6. Ending inside a block: no message for that block, `trunc` set on the packet end. A new sop in the middle: the packet in progress is abandoned silently (no packet end); messages already completed stay.
7. The counter is incremented as the block completes, in the same clock edge that registers the message. Reporting the register's new value would be one too many; the block's index is the value before the increment.
8. For a heartbeat (header only) the last count byte arrives in the same cycle as the eop; the register had not yet been loaded, so the comparison used the old count. The check now uses the byte on the wire in that cycle.
9. Flagged: type byte, length bytes (a truncation, a wrong count or an error), count. Not flagged: a payload byte (the corrupted message is accepted) and the sequence number (only a sequencer with memory can tell). Payloads are guarded by the UDP checksum (Chapter 9); sequence numbers by gap detection (Exercise 1).
10. After the bad length the framing is lost for the rest of the packet, but a sop restarts the parse, so the next packet is unaffected: on average 5.5 of 12 messages come out right, the rest are lost, and no garbage was accepted in 800 trials.
11. A garbage block must start with a type byte of the grammar (8 of 256) *and* be followed by exactly that type's length in its two length bytes (about 1 in 65,536 for random bytes), so about 1e-5 per garbage block; none was accepted in 800 packets.
12. For example: no zero-length or one-byte block was ever generated (the stimulus lacked those lengths); the offset counter does not saturate (no block over 255 bytes); reset does not stop a packet (the testbench reset only at the start); the stray-eop mutants (stray bytes never carried an eop).

## Chapter 16 -- hints for the exercises

1. Keep `next_seq` (64 bits); on a packet end set it to `seq + count`; compare a new packet's `seq` with it when the header completes (a 64-bit comparison is a carry chain: register it and use the next cycle). A packet with `seq + count <= next_seq` is a duplicate; with `seq > next_seq`, a gap of `seq - next_seq`. Extend `decode` with the same state and `random_packets` with replays and holes.
2. The grammar entry becomes `("name", "lp1")` (length prefix of one byte); the field select cannot be a fixed offset any more, so keep a running offset per message and a counter for the string; the generator emits a small sub-state per such field. Messages after it have offsets that depend on the string's length: the grammar must say that they are relative to it.
3. SoupBinTCP packets are `length(2) type(1) payload`: the same loop with a one-byte type in place of the Mold header; generate it by giving the generator a different framing preamble, then check against a model with its own struct layouts.
4. Walk the grammar in the same order and emit, per type, a `case` that shifts each field out most significant byte first; the test is `decode(encode(x)) == x` on random values, then compare with the parser's output.
5. Candidates: a mutant of the unreachable `default` branches (equivalent), or one that changes the width of a counter that can never fill (outside the contract).

## Chapter 17

1. The previous block ends wherever its length says, which is unrelated to the beat size; the next block's length bytes and body start in whatever lane follows. The parser must carry its position in the block across beats and process several bytes of different roles in one clock.
2. The number of valid bytes in the beat (1 to W). Only the last beat of a packet may have fewer than W (a packet that is abandoned without eop is cut to whole beats).
3. The next message can start in the same beat in which one completes, and its first bytes would shift into the same field registers. The snapshot copies the fields at the lane where the block completes.
4. At most one block completes per beat; a second completion is error 3, reported as an `X` event, the packet is abandoned and its end is flagged truncated. A second block's total length (L + 2) must be below W to share a beat with the end of the first, and a valid ITCH message is at least 14 bytes on the wire, so W of 15 or more is needed for valid traffic to do it.
5. The block takes L + 2 bytes. If the previous block ends in lane `e` (uniform over W lanes) the new block ends in the same beat when `e + L + 2 < W`, which holds for `W - L - 2` values of `e`: P = max(0, W - L - 2) / W.
6. 41 bytes is 6 beats at W = 8 (5 full and one of one byte): 41 / 48 = 85.4% of the bus.
7. Stage 1 runs the framing chain (state, counters, block lengths, errors) and registers, for each lane, whether it is a field byte, its offset in the body, the type, and whether a block completes there. Stage 2 uses the registered tags and the registered data to shift bytes into the field registers and take the snapshot, with no framing logic in its path.
8. Writing header bytes by an index computed from the position counter makes every lane's store a decoder driven by the chain's position variable, in front of 80-bit and 64-bit registers: more logic on the same path than a shift. The measured clock fell from 37 to 33 MHz (W = 4, iCE40).
9. The role of lane `j` depends on all earlier lanes (where blocks end is a function of the length bytes), so the logic is a chain W lanes deep. Breaking it takes speculation (compute every possible role in parallel and select) or a first stage that finds the boundaries from the length bytes alone.
10. That the straightforward design, simulated and correct, is too large for the book's flow at W = 8 in 15 minutes for both families and for all three versions. It does not say that W = 8 cannot be built, or how fast it would be.
11. One byte per clock at 125 MHz is 1 Gbit/s, which is gigabit Ethernet's rate (and ECP5 reaches 132 MHz). Ten gigabit is eight bytes at 156 MHz or more, and the wide design here does not get near it.
12. For example: a zero-length block in lane 0 (missing test: too rare an alignment, now an `alignments` stream); the type byte tagged as a field byte (code that cannot matter: the field selects already exclude offset 0).

## Chapter 17 -- hints for the exercises

1. For lane `j` assume a block starts at `j` (LENH at `j`, LENL at `j+1`, type at `j+2`): the role of every lane after `j` follows from the length read at `j`, `j+1`. Select by the actual `rem`/state at beat start. Speculating for every `j` costs about W times the per-lane logic but each is shallow; the selection is a mux tree.
2. Stage 1 needs only the length bytes and the remaining count: boundaries are `pos_k = pos_{k-1} + 2 + L_k`, a prefix sum whose terms are unknown until the length bytes are read, so pipeline it over two cycles or limit it to the lanes where a length can start.
3. The second slot needs its own field registers and snapshot (double the output registers); the rule becomes "a third completion is an error".
4. Replace the 8 per-lane type comparisons by one decode of the type byte shared by tags and lengths; the field selects are then comparisons against a one-hot vector.
5. Candidates: a mutant in the unreachable `default` of the state case (equivalent), or in the saturation value of the offset (outside the contract above 255 bytes only for blocks that are errors anyway).

## Chapter 18

1. So that the loss of a packet on one path does not lose it: the two copies take different routes. The arbiter forwards the first copy that arrives and drops the second as a duplicate; a copy that arrives after the packet was forwarded is behind `next` and ends at or before it.
2. It arrives with `d = seq - next > 0`. If a slot already has this number it is a duplicate; else it is stored in the lowest free slot (OVF if there is none). Later, when `next` reaches its number, the slot is "in order": it is released (one per cycle, with priority over the input), `next` advances by its count and the slot is freed. While it waits the window is a gap, and the gap timer runs.
3. When the window holds packets and none is in order (a gap) and the timer reaches TO with no request sent: request `[next, next + min(mind, 65535))`. If a request has been sent and the timer reaches TO2: the range is reported as skipped, `next` moves to the first stored packet, the arbiter continues.
4. A release and a skip both change `next` and the slots; a forward or a store in the same cycle would change them too, and the cycle's decisions are taken from the state at its start. So the input waits one cycle (`ready = 0`) rather than the design resolving two writers.
5. It is the property a user needs (every message once, in order, losses reported), it needs no knowledge of the internals, and it holds under any loss pattern, so it can be checked on random closed-loop runs. It does not check *when* things happen (the cycle model does), the kinds of the decisions (DUP, BAD, OVF) or the timer events, and it cannot see a loss at the end of the stream.
6. A packet is lost on both feeds with probability `p x p`.
7. At least (TO + answer time) / packet spacing packets: a gap stays open for that long and that many packets arrive behind the lost one. Smaller, the later packets are dropped (OVF) and asked for again: at 5% loss with 2 slots the arbiter fetched 4,530 messages for 5 packets that were really lost.
8. Longer than the skew between the feeds plus the jitter: a gap opened by loss on the first feed is closed by the second feed's copy at about that delay. Shorter, the arbiter asks for packets that are on their way (430 requests at TO = 2 for none needed).
9. The clock fell about as the inverse of the window (52 to 6 MHz from 1 to 16 slots on iCE40), the critical path 88 ns of logic at 16 slots. Storing the distance removed recomputation but the critical path was the minimum over the slots, written as a chain of comparators.
10. Each iteration of the loop compares with the result of the previous one, so the comparators are in series, PEND deep; a tree compares pairs in parallel and pairs of pairs, `log2(PEND)` deep.
11. A loss is revealed by a later packet with a higher number. If the last packets are lost on both feeds, or were dropped for lack of a slot, nothing follows them. A heartbeat with the next expected number would reveal it; this arbiter ignores heartbeats.
12. For example: the skip that does not wait for a request (a missing test: TO was always smaller than TO2); a forward that advances during a heartbeat (code that cannot matter: its count is 0); a skip that does not clear the request flag (equivalent: the next cycle is not a gap and clears it); reset that does not clear the slots (an Icarus semantics hole closed by powering the registers up with garbage).

## Chapter 18 -- hints for the exercises

1. A stale stored packet (its range lies entirely behind the new `next`) must be dropped, one that straddles `next` must be trimmed or reported BAD: in the distance representation a slot with distance below zero after the subtraction is stale; the model needs a rule and a test with a retransmission that covers two stored packets.
2. A heartbeat `(seq, 0)` with `seq` ahead of `next` opens a gap with no stored packet: the timer needs a `gap` that does not depend on a stored packet, with `mind` taken from the heartbeat's number (a register); then the request is for `[next, seq)`.
3. A bitmap of 512 bits (arrived or not) indexed by `seq mod 512` and a RAM of counts; the release is a lookup at `next`; the minimum is a priority search of the bitmap from `next` (a find-first-set on a rotated word), which is the part to pipeline.
4. Two ports into the classifier means two decisions in a cycle: the second can see the first's result (a duplicate in the same cycle) or the pair can be reduced to one by a rule (A first). The model must say which.
5. Candidates: a mutant in a counter's unreachable top bit (equivalent), or in the timer's width above any configured TO2 (outside the contract).

## Chapter 19

1. The top of book is the best bid and the best ask of a symbol, with their total shares. After every event the book reports the result code, the symbol, the best bid and ask (price, shares), the number of levels on each side and the number of orders in the table.
2. Both reduce an order's shares: an execution because a trade took them, a cancel because the owner withdrew them. The book's state changes in the same way, so they share a path. A REPLACE is a delete of the old order plus an add of the new one; if the add fails, the old order has already been removed (the one exception to "a failed event changes nothing").
3. ZERO shares, then DUPREF (the reference exists), then FULL (no free order slot), then LVL (a new level is needed and none is free). A duplicate is found before a full table because a duplicate would not use a slot: a full table with an existing reference must say DUPREF, not FULL. The mutation run found this ordering missing from the model's hand-checked scenarios.
4. One comparator per level compares its price with the incoming one; the position is the count of valid levels that are better. Because the levels are sorted and contiguous, the count is the index at which the price belongs (or the index of the equal level when there is a hit).
5. Insert: every level at or below position `p` moves down one place, the new level is written at `p`, in a single cycle. Remove: every level below the emptied one moves up one place, and the last valid entry becomes invalid. Both are shifts of the whole array, a mux per level in each direction.
6. The old order has to be removed and the new one added, and both touch the same table and possibly the same levels; doing both in one cycle would need two read-modify-writes on the same registers. The second phase uses latched copies of the new fields, and `in_ready` is 0 during it so no event arrives.
7. A search that compares every stored entry with the key at the same time, in one cycle. It costs one comparator (32 bits for the reference) and a mux per field per entry, so it grows linearly with the number of entries in area and badly in routing.
8. A dictionary of references to orders and of (symbol, side) to price-to-shares is the shortest correct statement of what a book is, with no sizes and no layout. It is independent of the RTL's arrays, so a disagreement means one of them is wrong.
9. The cost of the register-only book at seven sizes. Even 2 symbols, 2 levels and 16 orders is 4,949 LUTs on iCE40 at 19 MHz; 4 levels does not fit; 32 orders gives 13.3 MHz. The clock went to routing (52.9 ns of the path at NO = 32), from an order's valid bit through the lookup, the level search and the shift into the result register.
10. At a spread of 8 ticks the fullest side held 13.2 levels on average (p99 19, maximum 24). More than 8 because the mid moves and orders left behind keep their levels until executed or deleted. D of 2 to 3 times the spread gives under 1% rejected.
11. The control target of 64 live orders overshoots (the occupancy has mean 86.7, p99 100), so a table of 64 entries is full about half the time that an ADD arrives (50% rejected). 96 entries reject 1.6%, 128 none.
12. For example: the shift test with `>=` for `>` (equivalent: the new-level branch is tested first, so the shifted-down test is never reached for `i = p`); a duplicate checked after the full table (model mutant; a missing hand-checked scenario with a full table and a duplicate at once); an unknown reference reported with symbol 1 (model mutant; a missing hand-checked scenario for the symbol of an unknown REPLACE or DELETE).

## Chapter 19 -- hints for the exercises

1. The model must say whether two live references with the same hash are both allowed (then the overflow list is part of the contract and a full overflow list is a new result code) or whether the second is rejected; the test must include a deliberate collision, and a mutant that treats a collision as a hit must be caught.
2. Say what happens to the orders at the evicted level: they must be removed from the order table (or marked as having no level), otherwise a later EXEC on one of them reduces a level that no longer exists. Test an EXEC and a DELETE on an evicted order.
3. The rule on emptying the top level is a refill: the next level is read from the RAM and moved into the register array, which takes a number of cycles the model has to state (the top of book must not show an empty side while the RAM holds a level). The test is an event stream that empties the top level many times in a row.
4. The stock name (8 characters) is mapped to a symbol index by a small associative or hash table loaded before the session (stock directory messages); an unknown stock needs a result code, and the table size is another bound like `NS`.
5. Candidates: a mutant in the high bit of a level count that never exceeds `D` (equivalent), or in the symbol bits above `NS` (outside the contract: the input promises a valid symbol).

## Chapter 20

1. The order table is `NB` buckets of `K` ways and a reference can only go to the bucket `h(ref)`; if that bucket already holds `K` orders the ADD is refused whatever the rest of the table holds. The specification says it: FULL when the bucket of `h(ref) = (ref ^ ref>>8 ^ ref>>16 ^ ref>>24) mod NB` holds `K` orders. With 32 x 4 and a target of 64 live orders, 8.7% of the ADDs were refused.
2. K + 3 cycles: the accept cycle, K + 1 reads of the bucket (K ways and the last data) and one decision. The lookup always reads all the ways (there is no early exit), so the time does not depend on where, or whether, the reference was found; the decision cycle reports DUPREF.
3. `p` is the number of strictly better price levels on the side: the index of the order's level, or of the place a new level goes. The search reads one level per cycle from the best and decides `p + 1` cycles after the first read, so it takes `p + 2` cycles including the first.
4. The accept cycle is the cycle in which the engine takes the event off the input; the second phase of a REPLACE starts from the registers, with no new event, so it has a lookup (for the new reference) but no accept. If the new shares are zero the result is ZERO at once.
5. A registered write enable or address takes effect one cycle after the state that wants it, so the write would land in the wrong state; computing them from the current state writes in that state's cycle.
6. Shift down: a read of entry j is issued in cycle t, its data (registered) is on the output in t + 1 and is written to entry j + 1 in t + 1, while the read of j - 1 is issued; so one entry is read and a different one written in the same cycle, which a RAM with one read and one write port allows. Moving m entries takes m + 1 cycles, the first reading from the last valid entry down to the insertion index.
7. The number of levels on each side is a register that is reset, and says which words are valid, so stale words in the level RAM are never used. The order RAM has no such count: validity is a bit in each word, so every word must be cleared (`NB x K` cycles after reset).
8. Most events are at or near the best price, so `p` is small, and the deep levels are rarely visited: the mean barely changes. The worst case is an event at the worst price with shifts of the whole side, which grows with D, and the tail (the 99th percentile of REPLACE: 50 at D = 16, 53 at D = 32) follows.
9. (A) D bid levels of one order each and a REPLACE of the best order by a price better than all: the deletion shifts D - 1 levels up, the addition shifts D - 1 down. (B) the worst level holds two orders and one is replaced at the same price: the level search runs to the end twice and nothing shifts. A is the longest when shifts are costly, B only for D = 1; the closed form is the maximum over the structural cases.
10. The LUT count is almost constant (1,485 at 16 orders and 4 levels, 1,560 at 128 orders and 16 levels, 1,592 at 256 and 24): it is the control, the comparators on the one entry being read, the best-level registers and the pin wrapper. The capacity is in the RAM (block RAM on iCE40, `DP16KD` and LUT RAM on ECP5).
11. The path from the level RAM's read data or the state through the 32-bit price comparison, the choice of the next state and the counters, about 16 to 20 ns, half of it routing (50 to 58 MHz on iCE40). Register the comparison results at the RAM output and decide one cycle later (Exercise 1), at the cost of one more cycle per search.
12. For example: the lookup that keeps the last free way instead of the first (equivalent: the model does not say which way, and it changes neither a result nor a time; the RTL was simplified); an equal price counted as better in the level search (equivalent: the hit test comes first); the model whose hash ignores byte 1 (a missing hand-checked scenario with a reference above 255); the model that counts a bucket's fullness over one symbol only (a missing hand-checked scenario).

## Chapter 20 -- hints for the exercises

1. The comparison results are registered at the output of the level RAM: the decision uses the registered flags one cycle later, while the next read is already issued; so the search takes `p + 3` cycles, and `worst_case` and the table in the specification change by one cycle per search (two for a REPLACE). The clock should rise because the 32-bit compare is no longer in the same path as the state and counters; measure it.
2. The lookup needs the free way too, but for a reduction or DELETE only the match matters: stop at the cycle after the match, and the lookup costs `w + 3` for a reference in way `w`; the DUPREF/FULL events (ADDs) still read all the ways.
3. The rule on emptying the top level is a refill: the next level is read from the RAM and moved into the register array, a number of cycles the model must state; the worst case rises by the refill; test an event stream that empties the best level many times in a row.
4. A multiplicative hash (`(ref * odd constant) >> (32 - log2 NB)`) mixes all the bits; strided references stop being a worst case, but the model, the RTL and the mutants about the hash must all change; check the near-miss test still lands in the same bucket (its design assumes the XOR fold).
5. Candidates: a mutant in a counter's unreachable top bit (equivalent), or in the width of the wrapper's folded output (outside the contract).

## Chapter 21

1. A message is `(type, key, side, price, shares)`. A rule is `en`, `neg`, a type mask, symany or a symbol mask, sideany or a side, and one comparison each on price and shares against a constant. An answer is `mask` (bit r = rule r matched), `fire` (any bit) and `first` (the lowest matching rule). A rule matches when it is enabled and (its predicate xor `neg`) is true.
2. An unknown key gets `(found, index) = (0, 0)`, and index 0 is also a real symbol; if the symbol mask were applied to the index of an unknown key, a rule for symbol 0 would fire on every unknown symbol. The predicate therefore tests `found and symmask[index]`, and only `symany` admits a key that is not in the table.
3. In cycle `a + 4` (stage 1 reads the banks, stage 2 compares the keys, stage 3 compares the rules, the last stage forms mask, fire and first). With two comparison stages it is `a + 5`; the throughput is still one message per cycle.
4. A table write in cycle `w` lands at the end of cycle `w`; a lookup in cycle `w` reads the old contents, so the message of cycle `w` does not see it and the message of cycle `w + 1` does. A rule write in cycle `c` is seen by the messages whose rules are compared in cycle `c + 1` or later, that is, offered from cycle `c - 1` (compared in cycle `a + 2`), so the message of cycle `c - 1` does see it.
5. The `K` keys of a bucket are compared at once, so the lookup takes the same number of cycles whatever the `K` (and whatever is found); Chapter 20 read one way per cycle (K + 1 cycles) with one comparator. The price is `K` comparators and `K` RAM banks; the gain is a fixed, short latency and one lookup per cycle.
6. Row bit `b` is `key[b] ^ key[b+8] ^ key[b+16] ^ key[b+24]`; two keys with the same row and the same bits above the low `log2(NB)` positions must therefore have the same low bits (each can be recovered from the row and the bits at `b + 8`, `b + 16`, `b + 24`). This needs the bits `b + 8, ...` to be stored, so `log2(NB) <= 8`, that is `NB <= 256`.
7. The halves are compared separately in the first stage (`<` and `==` on bits 31:16 and on bits 15:0, registered); in the second, `lt = hi_lt | (hi_eq & lo_lt)` and `eq = hi_eq & lo_eq`, and the operator selects the result. A rule write must be seen at one well-defined moment, so every field of the rule (including the operators, the enable and the negation) is copied into the registers of the first stage, which reads the rule registers in cycle `a + 2` just as the one-stage design does.
8. The table is in RAM: more entries mean more RAM words, not more logic; the logic is the hash, the `K` comparators and the control, which do not depend on `NB`. Example A: 1,138 and 1,185 LUTs on iCE40 for 256 and 1,024 symbols.
9. With 8 rows Yosys uses LUT RAM, whose read is fast; with 64 or 256 rows it uses block RAM, whose clock-to-output delay (about 9 ns of logic with the key comparators on ECP5) is the whole critical path. Register the RAM's output before the comparators (one more stage, one more cycle of latency, and the table-write visibility rule moves with it).
10. The row is the low bits of the XOR of the four bytes; ASCII capital letters differ only in their low five bits, so the XOR of four of them takes at most 32 values, and the low 6 or 7 bits (the row) of a table with 64 or 128 or more rows cannot be spread over the table. A multiplicative hash takes the top bits of `key x constant`, to which every bit of the key contributes, so structured keys are spread like random ones.
11. `in_valid` must be 0: only the last valid register is reset, and the earlier stages are flushed by the idle input during the three reset cycles. Resetting every stage was redundant (each alone was an equivalent mutant), so the RTL resets one.
12. For example: the table write that ignores the valid bit (a missing test: deletions wrote key 0, so only a message with key 0 saw the difference; deletions now carry the old key); the 31-bit key comparison (equivalent: the low bit is implied by the row, so the RTL stores keys without their low `log2(NB)` bits and the mutant became one bit fewer than that); the model whose negated rule ignores the enable (a missing scenario, and the first one written did not tell them apart because its predicate was true).

## Chapter 21 -- hints for the exercises

1. The partial-key trick relies on the row being a XOR of key bits that can be solved for the low bits; the top bits of a product do not allow that, so the full key must be stored (more RAM width). The multiplier (32 x constant, a few adders or a DSP) is in front of the RAM address and probably needs its own stage; measure the refusals as in Example B, and note the near-miss test assumes the fold (keys one bit apart do not share a bucket under the new hash).
2. `shares * 100 >= price` is a multiplication by a constant in front of a 32 x 40-bit comparison; the model must say whether the product is computed in 64 bits (no overflow) or modulo 2^32; the clause is a new template field (an enable and an operator) per rule, so the cost scales with R.
3. The visibility rule becomes: a table write in cycle `w` is seen by the lookups of cycle `w + 1` or later as before only if the write also passes through the new stage; the cleanest statement is "the lookups whose bank read happens after the write"; the model's `look` dictionary does not change, but the latency does (`L = 5 + PIPE`).
4. Two messages of the same symbol in consecutive cycles read-modify-write the same counter: the second must see the first's increment. The usual fixes are forwarding from the stage's output to its input or a pipeline that processes one symbol per N cycles; the model states the result for back-to-back messages explicitly and a directed test uses them.
5. Candidates: a mutant in a rule field's reset (the other fields are never read while `en` is 0: equivalent), or in the top bit of the registered index when `NS` is 16 (outside the contract if the control plane never writes an index above 15).

## Chapter 22

1. `mid2 = Pa + Pb` (`PW + 1` bits, unsigned): half ticks, so it is exact (the mid is a half-integer in ticks when the spread is odd). `spread = Pa - Pb` (`PW + 1` bits, signed). `w = round_half_up(Qb 2^F / (Qa + Qb))` (`F + 1` bits). `imb = 2w - 2^F` (`F + 2` bits, signed; units of 2^-F). `micro = Pb 2^F + spread w` (`PW + F` bits; ticks x 2^F). All are 0 when a side has no shares.
2. One division is the expensive operation, and everything else can be built on its rounded result: `imb` is `2w - 2^F` exactly, and `micro` is an exact integer product and sum of `w`. So no number is rounded by two rules, the error bounds follow from one rounding, and the hardware needs one divider.
3. When both sides are present `Qb < D`, so `Qb / D < 1`: the integer part of the quotient is 0, and the remainder can start at `Qb`. Each step doubles the remainder and produces the next fraction bit, so `F` steps give the `F` fraction bits; the rounding looks at the next bit through the remainder.
4. An exact half rounds up on both sides: `Qb 2^F / D = j + 1/2` and `Qa 2^F / D = (2^F - j - 1) + 1/2`, each rounded up gives `j + 1` and `2^F - j`, a sum of `2^F + 1`. With no shares on a side the signals do not exist: `ok = 0` and every output is 0.
5. `w` is in `[0, 2^F]`, so `micro = Pb + spread x w / 2^F` is a weighted average of `Pb` and `Pa` (`Pb + spread x w` for any sign of the spread), and a weighted average lies between its two terms. A crossed book (negative spread) puts the microprice between the two prices all the same.
6. The imbalance error is at most one unit of 2^-F (the error of `w` is at most half a unit, and `imb = 2w - 2^F` doubles it); the microprice error is at most `spread / 2^(F+1)` (half a unit of `w` times the spread). The property run reaches both bounds exactly (the worst error seen is 1.0000 of each), at the exact halves.
7. In cycle `a + F + 4` for a book offered in cycle `a`. The pipelined divider accepts one book per cycle; the shared divider is busy from the cycle after it accepts until the answer is visible, and accepts again in cycle `a + F + 4`.
8. Each step is a stage with its own registers: the remainder, the total, the quotient so far and the values (price, spread, mid, ok) that the later stages need; the shared divider keeps one set. It gives up rate: one book per `F + 4` cycles, and waiting when books arrive faster.
9. The product `spread x w` is a 25 x 13-bit multiplication; without a DSP block it is a few thousand LUTs of adders (3,156 against 1,408 in total), and its carry chains are slower than the block's multiplier (83 against 106 MHz).
10. The multiplication stage: the DSP's multiplier with no pipeline registers inside it (about 9 ns). Use the DSP's own input and output registers or split the product in two stages (one more cycle of latency): Exercise 1.
11. `F = 10` for a hundredth of a tick (largest error 0.0097) and `F = 14` for a thousandth. The shared divider at its capacity (1.0 book per 16 cycles) has a mean wait of 928 cycles and the queue grows without bound; at 0.8 the mean wait is 29.5 cycles, at 0.48 it is 7.
12. For example: the redundant valid resets (equivalent, each alone: the stage before it is reset, which flushes it; removed from the RTL); the shared divider's extra step (equivalent: it begins in the cycle the next stage takes the result; the guard was removed); half-down rounding (a missing test: random shares almost never land on exact halves; `half_books` added).

## Chapter 22 -- hints for the exercises

1. The DSP block can register its inputs and outputs internally; whether Yosys uses them depends on the registers around the multiplier. Splitting `w` into halves (`w = w_hi 2^8 + w_lo`) gives two smaller products and an add; `L` becomes `F + 5`, and `sig_gold.run` and the testbench's tail change by one cycle; check the clock with nextpnr.
2. Two quotient bits per step need a comparison against `D`, `2D` and `3D` (or a subtract and a select); a radix-4 step costs about twice the LUTs of a radix-2 step and halves the cycles; `division()` must do the same steps, and the exact-half books must still hit exact halves.
3. A table of the reciprocal of the leading bits of `D` plus one Newton step `x(2 - Dx)` gives `w` to a few bits less than the exact quotient; the properties of Section 2 (the microprice between the prices, the bounds) no longer hold exactly, so the model must give its own error bound and the test must check it, and `micro` must be clamped if you want to keep the "between the two prices" property.
4. With four quantities the total needs `QW + 2` bits and the divider remainder one more bit; the microprice formula weights the best prices by the other side's quantity at the touch, and does not generalise directly: the weights of the second levels are a modelling choice that the specification must state.
5. Candidates: a mutant in a width above the contract (a share count above `2^QW`: outside the contract), or in the top bit of `cnt` (equivalent, as it never counts that high).
