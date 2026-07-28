.subckt output_stage_half_outp intm OUTP vbias_n VDD VSS
M3 OUTP intm VDD VDD pch_lvt l=120.0n w=2u m=12
M6 OUTP vbias_n VSS VSS nch_lvt l=120.0n w=2u m=6
.ends output_stage_half_outp