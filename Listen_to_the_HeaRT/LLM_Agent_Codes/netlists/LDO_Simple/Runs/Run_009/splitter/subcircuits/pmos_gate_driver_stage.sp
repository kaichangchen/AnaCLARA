.subckt pmos_gate_driver_stage gnd iref_snk vdd net7 net2
M6 gnd net7 net2 vdd pmos l=l_eab_p w=w_eab_p*1 m=1 nf=1 sd=220.0n
M5 net2 iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
.ends pmos_gate_driver_stage