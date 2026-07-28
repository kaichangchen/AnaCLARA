.subckt bias_generator_vbiasn VBIAS_P vbias_n VDD VSS
M5 VBIAS_P VBIAS_P VDD VDD pch l=120.0n w=2u m=8
M7 vbias_n VBIAS_P VDD VDD pch l=120.0n w=2u m=8
M4 vbias_n vbias_n VSS VSS nch_lvt l=120.0n w=2u m=4
.ends bias_generator_vbiasn