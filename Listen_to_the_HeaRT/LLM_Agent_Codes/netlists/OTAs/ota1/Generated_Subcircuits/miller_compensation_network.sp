.subckt miller_compensation_network OUTP OUTM intm intp VDD VSS
M23 net047 VSS intm VDD pch_lvt l=120.0n w=2u m=12
M25 net037 VSS intp VDD pch_lvt l=120.0n w=2u m=12
C0 OUTP net047 cfmom_2t nr=210 lr=13.0u w=70n s=70n stm=3 spm=6 m=1
C1 OUTM net037 cfmom_2t nr=210 lr=13.0u w=70n s=70n stm=3 spm=6 m=1
.ends miller_compensation_network