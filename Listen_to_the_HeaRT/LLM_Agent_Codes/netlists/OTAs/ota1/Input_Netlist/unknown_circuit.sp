.subckt ota1 INM INP OUTM OUTP VBIAS_P VDD VREF VSS
MP1b intp VBIAS_P VDD VDD pch l=120.0n w=2u m=20
MP1a intm VBIAS_P VDD VDD pch l=120.0n w=2u m=20
M5 VBIAS_P VBIAS_P VDD VDD pch l=120.0n w=2u m=8
M7 vbias_n VBIAS_P VDD VDD pch l=120.0n w=2u m=8
M20 net028 VBIAS_P VDD VDD pch l=120.0n w=2u m=8
MP1c net020 VBIAS_P VDD VDD pch l=120.0n w=2u m=8
M17 net025 VREF net020 VDD pch_lvt l=120.0n w=2u m=8
M19 net025 VREF net028 VDD pch_lvt l=120.0n w=2u m=8
M25 net037 VSS intp VDD pch_lvt l=120.0n w=2u m=12
M23 net047 VSS intm VDD pch_lvt l=120.0n w=2u m=12
M1 OUTM intp VDD VDD pch_lvt l=120.0n w=2u m=12
M3 OUTP intm VDD VDD pch_lvt l=120.0n w=2u m=12
M18 vcmfb OUTM net028 VDD pch_lvt l=120.0n w=2u m=8
M15 vcmfb OUTP net020 VDD pch_lvt l=120.0n w=2u m=8
M12 net025 net025 VSS VSS nch_lvt l=120.0n w=2u m=2
M6 OUTP vbias_n VSS VSS nch_lvt l=120.0n w=2u m=6
M9 OUTM vbias_n VSS VSS nch_lvt l=120.0n w=2u m=6
M10 net7 vbias_n VSS VSS nch_lvt l=120.0n w=2u m=16
M11 net7 vcmfb VSS VSS nch_lvt l=120.0n w=2u m=4
M4 vbias_n vbias_n VSS VSS nch_lvt l=120.0n w=2u m=4
M13 vcmfb vcmfb VSS VSS nch_lvt l=120.0n w=2u m=2
M0 intp INM net7 VSS nch_25ud18 l=500n w=5u m=12
M2 intm INP net7 VSS nch_25ud18 l=500n w=5u m=12
C0 OUTP net047 cfmom_2t nr=210 lr=13.0u w=70n s=70n stm=3 spm=6 m=1 
C1 OUTM net037 cfmom_2t nr=210 lr=13.0u w=70n s=70n stm=3 spm=6 m=1 
.ends

