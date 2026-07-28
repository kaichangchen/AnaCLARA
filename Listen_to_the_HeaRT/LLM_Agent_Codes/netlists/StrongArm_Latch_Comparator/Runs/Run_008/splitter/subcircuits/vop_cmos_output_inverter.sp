.subckt vop_cmos_output_inverter vss vdd Vx Vop
M2 Vop Vx vss vss nmos w=120n l=60n nf=1 m=1
M17 Vop Vx vdd vdd pmos w=120n l=60n nf=1 m=1
.ends vop_cmos_output_inverter