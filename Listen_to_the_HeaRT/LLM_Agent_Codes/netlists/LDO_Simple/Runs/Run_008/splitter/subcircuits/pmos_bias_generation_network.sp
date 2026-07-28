.subckt pmos_bias_generation_network iref_snk vdd
M1 iref_snk iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
.ends pmos_bias_generation_network