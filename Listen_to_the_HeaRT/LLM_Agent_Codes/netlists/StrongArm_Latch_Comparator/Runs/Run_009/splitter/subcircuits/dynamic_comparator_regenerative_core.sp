.subckt dynamic_comparator_regenerative_core vss vdd Vin Vip clk VP VQ Vx Vy
MN2 VQ Vin net17 vss nmos w=W2 l=L2 nf=1 m=1
MN4 Vx Vy VP vss nmos w=W3 l=L3 nf=1 m=1
MN1 net17 clk vss vss nmos w=W l=L1 nf=1 m=1
MN3 Vy Vx VQ vss nmos w=W3 l=L3 nf=1 m=1
MN0 VP Vip net17 vss nmos w=W2 l=L2 nf=1 m=1
MN10 VP clk vdd vdd pmos w=W6 l=L6 nf=1 m=1
MN8 Vy clk vdd vdd pmos w=W5 l=L5 nf=1 m=1
MN6 Vx Vy vdd vdd pmos w=W4 l=L4 nf=1 m=1
MN5 Vy Vx vdd vdd pmos w=W4 l=L4 nf=1 m=1
MN7 Vx clk vdd vdd pmos w=W5 l=L5 nf=1 m=1
MN9 VQ clk vdd vdd pmos w=W6 l=L6 nf=1 m=1
.ends dynamic_comparator_regenerative_core