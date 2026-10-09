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
