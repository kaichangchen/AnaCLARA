.subckt pmos_diode_bias_generator vdd iref_snk
M1 iref_snk iref_snk vdd vdd pmos l=l_cs_p w=w_cs_p*1 m=1 nf=1
.ends pmos_diode_bias_generator