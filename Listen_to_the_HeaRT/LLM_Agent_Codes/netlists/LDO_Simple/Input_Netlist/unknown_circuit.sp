** Cell name: ldo_pmos_v1_auto
** View name: schematic

.subckt ldo_pmos_v1_auto gnd iref_snk vdd vin vo
M6 gnd net7 net2 vdd pmos l=l_eab_p w=w_eab_p*1 m=1 nf=1 sd=220.0n
M5 net2 iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
M4 net7 vin net5 vdd pmos l=l_eai_p w=w_eai_p*1 m=1 nf=1 sd=220.0n
M3 net6 fb net5 vdd pmos l=l_eai_p w=w_eai_p*1 m=1 nf=1 sd=220.0n
M2 net5 iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
M1 iref_snk iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
M0 vo net2 vdd vdd pmos l=l_power_p w=w_power_p*1 m=1 nf=1
R0 net1 vo res r0
C0 net7 net1 cap c0
CL vo GND cap cload
R1 vo fb res r1
R2 fb gnd res r2
M8 net6 net6 gnd gnd nmos l=l_eal_n w=w_eal_n*1 m=1 nf=1 sd=220.0n
M7 net7 net6 gnd gnd nmos l=l_eal_n w=w_eal_n*1 m=1 nf=1 sd=220.0n
.ends ldo_pmos_v1_auto
** End of subcircuit definition.

