// verilator lint_off DECLFILENAME
// Chapter 2: a frame recognizer written three ways. Input: a stream of bytes (in_valid marks the cycles that carry one).
// A frame is: SOF byte 0xA5, a LEN byte (1 to 16), LEN payload bytes, an END byte 0x5A. A bad LEN or a bad END aborts the frame.
// Outputs, all registered (they report the byte consumed in the previous cycle): pay_v = a payload byte, done = a frame ended correctly, err = a frame was aborted. busy = a frame is in progress (from the state).
// frame_a: ONE always_ff block holding state, counter and outputs together (compact, easy to get wrong).
// frame_b: TWO processes: a combinational next-state function (always_comb, enum state, unique case) and a registered update. The textbook style.
// frame_c: ONE-HOT state, one flip-flop per state; fast decoding at a cost in flip-flops, common in FPGAs.
module frame_a (input logic clk, input logic rst, input logic in_valid, input logic [7:0] in_byte,
    output logic busy, output logic pay_v, output logic done, output logic err);
    logic [1:0] st; logic [4:0] cnt;      // 0 idle, 1 len, 2 data, 3 end
    assign busy = (st != 2'd0);
    always_ff @(posedge clk) begin
        pay_v <= 1'b0; done <= 1'b0; err <= 1'b0;
        if (rst) begin st <= 2'd0; cnt <= 5'd0; end
        else if (in_valid) begin
            case (st)
                2'd0: if (in_byte == 8'hA5) st <= 2'd1;
                2'd1: if (in_byte >= 8'd1 && in_byte <= 8'd16) begin cnt <= in_byte[4:0]; st <= 2'd2; end else begin err <= 1'b1; st <= 2'd0; end
                2'd2: begin pay_v <= 1'b1; cnt <= cnt - 5'd1; if (cnt == 5'd1) st <= 2'd3; end
                default: begin if (in_byte == 8'h5A) done <= 1'b1; else err <= 1'b1; st <= 2'd0; end
            endcase
        end
    end
endmodule
module frame_b (input logic clk, input logic rst, input logic in_valid, input logic [7:0] in_byte,
    output logic busy, output logic pay_v, output logic done, output logic err);
    typedef enum logic [1:0] {IDLE, LEN, DATA, FIN} state_t;
    state_t st, nx; logic [4:0] cnt, cnt_n; logic pay_n, done_n, err_n;
    assign busy = (st != IDLE);
    always_comb begin
        nx = st; cnt_n = cnt; pay_n = 1'b0; done_n = 1'b0; err_n = 1'b0;
        if (in_valid) begin
            unique case (st)
                IDLE: if (in_byte == 8'hA5) nx = LEN;
                LEN: if (in_byte >= 8'd1 && in_byte <= 8'd16) begin cnt_n = in_byte[4:0]; nx = DATA; end else begin err_n = 1'b1; nx = IDLE; end
                DATA: begin pay_n = 1'b1; cnt_n = cnt - 5'd1; if (cnt == 5'd1) nx = FIN; end
                FIN: begin if (in_byte == 8'h5A) done_n = 1'b1; else err_n = 1'b1; nx = IDLE; end
            endcase
        end
    end
    always_ff @(posedge clk) begin
        if (rst) begin st <= IDLE; cnt <= 5'd0; pay_v <= 1'b0; done <= 1'b0; err <= 1'b0; end
        else begin st <= nx; cnt <= cnt_n; pay_v <= pay_n; done <= done_n; err <= err_n; end
    end
endmodule
module frame_c (input logic clk, input logic rst, input logic in_valid, input logic [7:0] in_byte,
    output logic busy, output logic pay_v, output logic done, output logic err);
    logic s_idle, s_len, s_data, s_fin; logic [4:0] cnt;                    // exactly one of the four is 1
    logic good_len; assign good_len = (in_byte >= 8'd1) && (in_byte <= 8'd16);
    assign busy = !s_idle;
    always_ff @(posedge clk) begin
        pay_v <= 1'b0; done <= 1'b0; err <= 1'b0;
        if (rst) begin s_idle <= 1'b1; s_len <= 1'b0; s_data <= 1'b0; s_fin <= 1'b0; cnt <= 5'd0; end
        else if (in_valid) begin
            s_idle <= (s_idle && in_byte != 8'hA5) || (s_len && !good_len) || s_fin;
            s_len  <= (s_idle && in_byte == 8'hA5);
            s_data <= (s_len && good_len) || (s_data && cnt != 5'd1);
            s_fin  <= (s_data && cnt == 5'd1);
            if (s_len && good_len) cnt <= in_byte[4:0];
            if (s_data) begin cnt <= cnt - 5'd1; pay_v <= 1'b1; end
            if (s_len && !good_len) err <= 1'b1;
            if (s_fin) begin if (in_byte == 8'h5A) done <= 1'b1; else err <= 1'b1; end
        end
    end
endmodule
