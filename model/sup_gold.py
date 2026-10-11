#!/usr/bin/env python3
"""Chapter 27: the specification of the supervisor (rtl/sup.sv) and of the reset generator (rtl/sup.sv `rst_gen`).
THE SUPERVISOR is a state machine with four states and a latched cause. The inputs of a cycle: go (a pulse from the control plane), trip (a pulse: an external trip), feed (the feed carried a byte), slot (the strategy slot is held), fault (the tracker's sticky fault), sess (the transmitter's session state; ACTIVE = 2), tx_ready, quiet (nothing in flight: the lifecycle is idle, no order is held, no answer is being sent).
  INIT   after reset, for WARM cycles (the cycle count is the first cycle after reset = 0: READY is visible from cycle WARM). The units are clearing their RAMs; nothing may leave.
  READY  waiting: `go` with the session ACTIVE makes it RUN (visible the next cycle).
  RUN    orders may leave. Two counters: fc counts the cycles since the last feed byte (cleared by a byte), sc counts the cycles the slot has been held (cleared when it is free); both are 0 on entering RUN and need no saturation, since a count that reaches its limit leaves RUN in the next cycle. In every RUN cycle the five causes are evaluated: f_t (fc >= FT: the feed has been silent for FT cycles; fc is the count BEFORE this cycle's byte, so a byte in the cycle fc reaches FT does not save the session), s_t (sc >= ST), trip, fault, and the session is not ACTIVE. If any is true the state becomes SAFE in the next cycle and `cause` is latched with a bit for every cause that was true (bit 0 feed, 1 stall, 2 external trip, 3 fault, 4 session).
  SAFE   absorbing: only a reset leaves it. The logout request `cq` is offered in every SAFE cycle in which it has not yet been accepted, the session is ACTIVE, the transmitter is ready and nothing is in flight; the cycle it is offered is counted as accepted (the transmitter takes it when it is ready).
  kill = (state != RUN) in every cycle (a level the gate samples when an order is offered).
Time: the state, kill, cq and cause visible in cycle c are those after the updates of cycles up to c - 1 (cq is a function of the state and of the inputs of cycle c).
THE RESET GENERATOR. rst_in asserts the unit reset (rst_u) in the same cycle (asynchronously in the RTL; the specification samples it at the clock edge, and a pulse must span at least one clock edge). After rst_in goes away rst_u stays high for 2 + RSTN more cycles: two for the release synchroniser, RSTN for the stretch."""
import random
INIT, READY, RUN, SAFE = range(4)
SN = ["INIT", "READY", "RUN", "SAFE"]
CAUSES = ["feed", "stall", "trip", "fault", "session"]
ACTIVE = 2
class Sup:
    def __init__(self, ft=100, st=100, warm=48):
        self.ft, self.st, self.warm = ft, st, warm; self.state = INIT; self.cnt = 0; self.fc = 0; self.sc = 0; self.sent = 0; self.cause = 0
    def step(self, go=0, trip=0, feed=0, slot=0, fault=0, sess=ACTIVE, tx_ready=1, quiet=1):
        """-> (state, kill, cq, cause) visible in this cycle; then the update"""
        cq = int(self.state == SAFE and not self.sent and sess == ACTIVE and tx_ready and quiet)
        out = (self.state, int(self.state != RUN), cq, self.cause)
        f_t = self.fc >= self.ft; s_t = self.sc >= self.st
        now = int(f_t) | int(s_t) << 1 | int(bool(trip)) << 2 | int(bool(fault)) << 3 | int(sess != ACTIVE) << 4
        if self.state == INIT:
            self.cnt += 1
            if self.cnt >= self.warm: self.state = READY
        elif self.state == READY:
            if go and sess == ACTIVE: self.state = RUN
        elif self.state == RUN:
            self.fc = 0 if feed else self.fc + 1; self.sc = self.sc + 1 if slot else 0
            if now: self.state = SAFE; self.cause = now
        else:
            if cq: self.sent = 1
        return out
    def reset(self): self.__init__(self.ft, self.st, self.warm)
class RstGen:
    def __init__(self, rstn=8): self.rstn = rstn; self.r1 = 1; self.r2 = 1; self.cnt = rstn
    def step(self, rst_in):
        """-> rst_u visible in this cycle (rst_in is sampled before the edge; asserting is immediate)"""
        if rst_in: self.r1 = 1; self.r2 = 1
        out = int(self.r2 or self.cnt != 0)
        if self.r2: self.cnt = self.rstn                                                  # the stretch counter is loaded at every edge while r2 is high (also while rst_in is)
        elif self.cnt: self.cnt -= 1
        if not rst_in: self.r2 = self.r1; self.r1 = 0
        return out
def selftest():
    # the supervisor, worked by hand: FT 5, ST 4, WARM 3
    S = Sup(5, 4, 3); o = [S.step() for _ in range(3)]; assert [x[0] for x in o] == [INIT, INIT, INIT] and S.state == READY
    assert S.step()[0] == READY and S.step(go=1, sess=1)[0] == READY and S.state == READY          # go with the session not ACTIVE: stays
    assert S.step(go=1)[0] == READY and S.state == RUN and S.step(feed=1)[0:2] == (RUN, 0)
    # silence: fc 0 -> 1 .. 5; the cycle it is 5 (6 cycles after the byte) trips
    for i in range(5): assert S.step()[0] == RUN, i
    assert S.fc == 5 and S.step()[0] == RUN and S.state == SAFE and S.cause == 1                  # the cycle fc = 5 is evaluated: f_t
    assert S.step() == (SAFE, 1, 1, 1) and S.step() == (SAFE, 1, 0, 1)                            # the logout is offered once
    # a byte in the cycle fc reaches FT does not save it
    S = Sup(5, 4, 1); S.step(); S.step(go=1); S.step(feed=1)
    for i in range(5): S.step()
    assert S.step(feed=1)[0] == RUN and S.state == SAFE and S.cause == 1
    # stall: slot held for ST cycles
    S = Sup(50, 4, 1); S.step(); S.step(go=1); S.step(feed=1)
    for i in range(4): S.step(slot=1, feed=1)
    assert S.state == RUN and S.step(slot=1, feed=1)[0] == RUN and S.state == SAFE and S.cause == 2
    S = Sup(50, 4, 1); S.step(); S.step(go=1); S.step(feed=1)
    for i in range(3): S.step(slot=1, feed=1)
    S.step(slot=0, feed=1)
    for i in range(3): S.step(slot=1, feed=1)
    assert S.state == RUN                                                                         # the slot freed in between: the count restarted
    # every cause alone, and two together; no logout when the session is not ACTIVE or the pipeline is busy
    for k, kw in enumerate([dict(trip=1), dict(fault=1), dict(sess=4)]):
        S = Sup(50, 50, 1); S.step(); S.step(go=1); S.step(feed=1); S.step(feed=1, **kw); assert S.state == SAFE and S.cause == [4, 8, 16][k], k
    S = Sup(50, 50, 1); S.step(); S.step(go=1); S.step(feed=1); S.step(feed=1, trip=1, fault=1); assert S.cause == 12
    assert S.step(tx_ready=0)[2] == 0 and S.step(quiet=0)[2] == 0 and S.step(sess=3)[2] == 0 and S.step()[2] == 1 and S.step()[2] == 0
    # the reset generator: RSTN 3
    R = RstGen(3); assert [R.step(1) for _ in range(2)] == [1, 1]
    assert [R.step(0) for _ in range(8)] == [1, 1, 1, 1, 1, 0, 0, 0]
    assert R.step(1) == 1 and [R.step(0) for _ in range(6)] == [1, 1, 1, 1, 1, 0]                 # a one-cycle pulse is stretched as well
    return True
if __name__ == "__main__": print("selftest", selftest())
