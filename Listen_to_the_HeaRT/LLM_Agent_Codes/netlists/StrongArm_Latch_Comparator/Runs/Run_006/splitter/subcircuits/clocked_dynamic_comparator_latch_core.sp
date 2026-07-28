.subckt clocked_dynamic_comparator_latch_core vss vdd Vin Vip clk Vx Vy
MN2 VQ Vin net17 vss nmos w=W2 l=L2 nf=1 m=1
MN4 Vx Vy VP vss nmos w=W3 l=L3 nf=1 m=1
MN1 net17 clk vss vss nmos w=W l=L1 nf=1 m=1
MN3 Vy Vx VQ vss nmos w=W3 l=L3 nf=1 m=1
MN0 VP Vip net17 vss nmos w=W2 l=L2 nf=1 m=1
C3 Vy vss cap C3
C2 Vx vss cap C2
C0 VP vss cap C0
C1 VQ vss cap C1
MN10 VP clk vdd vdd pmos w=W6 l=L6 nf=1 m=1
MN8 Vy clk vdd vdd pmos w=W5 l=L5 nf=1 m=1
MN6 Vx Vy vdd vdd pmos w=W4 l=L4 nf=1 m=1
MN5 Vy Vx vdd vdd pmos w=W4 l=L4 nf=1 m=1
MN7 Vx clk vdd vdd pmos w=W5 l=L5 nf=1 m=1
MN9 VQ clk vdd vdd pmos w=W6 l=L6 nf=1 m=1
.ends clocked_dynamic_comparator_latch_core