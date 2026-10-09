"""Chapter 16: the message grammar the parser generator reads. A message is a type byte followed by fixed-size big-endian fields, in order; `length` is the total length of the message in bytes, type byte included (the length a MoldUDP64 block carries). Field names are shared across messages: a name has one width everywhere. The layouts are those of NASDAQ TotalView-ITCH 5.0 as the author remembers them (Add Order, Add Order with MPID, Order Executed, Order Cancel, Order Delete, Order Replace, Trade, System Event); they were NOT checked against the specification document, which this sandbox cannot fetch, so treat them as a realistic grammar, not as the exchange's.
MoldUDP64 (header: session 10 bytes, sequence number 8, message count 2; then `count` blocks of a 2-byte length and a message) is wired into the generator, not described here."""
ITCH = {
    "S": [("locate", 2), ("tracking", 2), ("ts", 6), ("event", 1)],
    "A": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("side", 1), ("shares", 4), ("stock", 8), ("price", 4)],
    "F": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("side", 1), ("shares", 4), ("stock", 8), ("price", 4), ("mpid", 4)],
    "E": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("shares", 4), ("match", 8)],
    "X": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("shares", 4)],
    "D": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8)],
    "U": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("newref", 8), ("shares", 4), ("price", 4)],
    "P": [("locate", 2), ("tracking", 2), ("ts", 6), ("ref", 8), ("side", 1), ("shares", 4), ("stock", 8), ("price", 4), ("match", 8)],
}
def length(msg): return 1 + sum(n for _, n in msg)
def fields(g):
    """-> ordered {name: bytes} over the whole grammar; a name with two widths is an error."""
    out = {}
    for t, m in g.items():
        for nm, n in m:
            if out.setdefault(nm, n) != n: raise ValueError(f"field {nm} has two widths")
    return out
