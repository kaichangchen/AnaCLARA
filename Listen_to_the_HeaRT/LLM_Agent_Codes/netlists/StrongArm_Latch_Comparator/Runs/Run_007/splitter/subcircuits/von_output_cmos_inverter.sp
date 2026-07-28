.subckt von_output_cmos_inverter vss vdd Vy Von
M3 Von Vy vss vss nmos w=120n l=60n nf=1 m=1
M16 Von Vy vdd vdd pmos w=120n l=60n nf=1 m=1
.ends von_output_cmos_inverter