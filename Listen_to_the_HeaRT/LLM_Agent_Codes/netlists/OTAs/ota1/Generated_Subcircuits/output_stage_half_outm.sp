.subckt output_stage_half_outm intp OUTM vbias_n VDD VSS
M1 OUTM intp VDD VDD pch_lvt l=120.0n w=2u m=12
M9 OUTM vbias_n VSS VSS nch_lvt l=120.0n w=2u m=6
.ends output_stage_half_outm