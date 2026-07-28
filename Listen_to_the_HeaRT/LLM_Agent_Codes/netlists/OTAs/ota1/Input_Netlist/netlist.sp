.subckt ota1 INM INP OUTM OUTP VBIAS_P VDD VREF VSS
MMP1b intp VBIAS_P VDD VDD pch l=120.0n w=2u m=20
MMP1a intm VBIAS_P VDD VDD pch l=120.0n w=2u m=20
MM5 VBIAS_P VBIAS_P VDD VDD pch l=120.0n w=2u m=8
MM7 vbias_n VBIAS_P VDD VDD pch l=120.0n w=2u m=8
MM20 net028 VBIAS_P VDD VDD pch l=120.0n w=2u m=8
MMP1c net020 VBIAS_P VDD VDD pch l=120.0n w=2u m=8
MM17 net025 VREF net020 VDD pch_lvt l=120.0n w=2u m=8
MM19 net025 VREF net028 VDD pch_lvt l=120.0n w=2u m=8
MM25 net037 VSS intp VDD pch_lvt l=120.0n w=2u m=12
MM23 net047 VSS intm VDD pch_lvt l=120.0n w=2u m=12
MM1 OUTM intp VDD VDD pch_lvt l=120.0n w=2u m=12
MM3 OUTP intm VDD VDD pch_lvt l=120.0n w=2u m=12
MM18 vcmfb OUTM net028 VDD pch_lvt l=120.0n w=2u m=8
MM15 vcmfb OUTP net020 VDD pch_lvt l=120.0n w=2u m=8
MM12 net025 net025 VSS VSS nch_lvt l=120.0n w=2u m=2
MM6 OUTP vbias_n VSS VSS nch_lvt l=120.0n w=2u m=6
MM9 OUTM vbias_n VSS VSS nch_lvt l=120.0n w=2u m=6
MM10 net7 vbias_n VSS VSS nch_lvt l=120.0n w=2u m=16
MM11 net7 vcmfb VSS VSS nch_lvt l=120.0n w=2u m=4
MM4 vbias_n vbias_n VSS VSS nch_lvt l=120.0n w=2u m=4
MM13 vcmfb vcmfb VSS VSS nch_lvt l=120.0n w=2u m=2
MM0 intp INM net7 VSS nch_25ud18 l=500n w=5u m=12
MM2 intm INP net7 VSS nch_25ud18 l=500n w=5u m=12
XC0 OUTP net047 cfmom_2t nr=210 lr=13.0u w=70n s=70n stm=3 spm=6 m=1 
XC1 OUTM net037 cfmom_2t nr=210 lr=13.0u w=70n s=70n stm=3 spm=6 m=1 
.ends

