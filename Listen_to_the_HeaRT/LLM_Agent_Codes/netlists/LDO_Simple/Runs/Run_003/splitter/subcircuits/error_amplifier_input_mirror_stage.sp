.subckt error_amplifier_input_mirror_stage gnd iref_snk vdd vin fb net7
M4 net7 vin net5 vdd pmos l=l_eai_p w=w_eai_p*1 m=1 nf=1 sd=220.0n
M3 net6 fb net5 vdd pmos l=l_eai_p w=w_eai_p*1 m=1 nf=1 sd=220.0n
M2 net5 iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
M8 net6 net6 gnd gnd nmos l=l_eal_n w=w_eal_n*1 m=1 nf=1 sd=220.0n
M7 net7 net6 gnd gnd nmos l=l_eal_n w=w_eal_n*1 m=1 nf=1 sd=220.0n
.ends error_amplifier_input_mirror_stage