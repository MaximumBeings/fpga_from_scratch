// Chapter 6: a synchronous FIFO with first-word fall-through, DEPTH words of W bits (DEPTH need not be a power of two), and a library of injected bugs for comparing verification techniques.
// Specification: a write is accepted when the FIFO is not full, a read when it is not empty (a simultaneous read and write at full or at empty accepts only the one the state allows); rd_data is the oldest word whenever empty is 0; count is the number of words held.
// BUG = 0 is the correct design. BUG = 1..6 each inject one realistic mistake:
//   1 a write when full is accepted: it overwrites the oldest word (overflow not blocked)
//   2 a simultaneous read and write with exactly one word held: the count goes to 0 instead of staying at 1
//   3 the write pointer wraps one word late, so after the first lap words are written outside the array
//   4 a simultaneous read and write when empty: the read is accepted as well, so the word just written is lost
//   5 a read when empty is accepted: the count underflows
//   6 a write of the data value 0xA5 when DEPTH - 1 words are held is lost (a data-dependent corner)
module sfifo #(parameter int W = 8, parameter int DEPTH = 6, parameter int BUG = 0) (
    input logic clk, input logic rst, input logic wr_en, input logic [W-1:0] wr_data, input logic rd_en,
    output logic [W-1:0] rd_data, output logic full, output logic empty, output logic [$clog2(DEPTH+1)-1:0] count);
    localparam int PW = $clog2(DEPTH), CW = $clog2(DEPTH + 1);
    localparam logic [CW-1:0] DEP = CW'(DEPTH), DEPM1 = CW'(DEPTH - 1);   // sized constants for the comparisons
    localparam logic [PW:0] LAST = (PW + 1)'(DEPTH - 1), LATE = (PW + 1)'(DEPTH);
    logic [W-1:0] mem [DEPTH]; logic [PW:0] wp, rp;                    // one extra pointer bit: BUG 3 needs to count past DEPTH - 1
    logic do_wr, do_rd;
    assign full = (count == DEP);
    assign empty = (count == '0);
    assign rd_data = mem[rp[PW-1:0]];
    always_comb begin
        do_wr = wr_en && !full; do_rd = rd_en && !empty;
        if (BUG == 1) do_wr = wr_en;
        if (BUG == 4 && wr_en && rd_en && empty) do_rd = 1'b1;
        if (BUG == 5) do_rd = rd_en;
        if (BUG == 6 && wr_en && wr_data == 8'hA5 && count == DEPM1) do_wr = 1'b0;
    end
    always_ff @(posedge clk) begin
        if (rst) begin wp <= '0; rp <= '0; count <= '0; end
        else begin
            if (do_wr) begin mem[wp[PW-1:0]] <= wr_data; wp <= (wp == ((BUG == 3) ? LATE : LAST)) ? '0 : wp + 1'b1; end
            if (do_rd) rp <= (rp == LAST) ? '0 : rp + 1'b1;
            case ({do_wr, do_rd})
                2'b10: if (count != DEP) count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                2'b11: if (BUG == 2 && count == CW'(1)) count <= '0;
                default: ;
            endcase
        end
    end
endmodule
