.subckt ota3 INM INP OUTM OUTP VBN1 VDD VREF VSS
M93 VCMFB3 VREF net058 VSS nch l=200n w=2.2u m=4
M60 net057 net056 net058 VSS nch l=200n w=2.2u m=4
M105 net058 VBN VSS VSS nch l=400n w=11.0u m=8
M13 OUTM VOP2 VSS VSS nch l=400n w=2.5u m=16
M113 OUTP VOM2 VSS VSS nch l=400n w=2.5u m=16
M110 VOM2 VCMFB2 VSS VSS nch l=400n w=2.5u m=8
M102 VOM2 VBN VSS VSS nch l=400n w=11.0u m=4
M18 VOP2 VBN VSS VSS nch l=400n w=11.0u m=4
M75 VOP2 VCMFB2 VSS VSS nch l=400n w=2.5u m=8
M106 VOP1 VBN1 net2 VSS nch l=200n w=6u m=10
M3 VOM1 VBN1 net4 VSS nch l=200n w=6u m=10
M4 net1 VBN VSS VSS nch l=400n w=11.0u m=28
M96 VBP1 VBN VSS VSS nch l=400n w=11.0u m=4
M97 VBP VBN VSS VSS nch l=400n w=11.0u m=4
M21 VBN VBN VSS VSS nch l=400n w=11.0u m=4
M24 VBN1 VBN1 VBN VSS nch l=1u w=6u m=10
M12 net4 INP net1 VSS nch_25ud18 l=800n w=9u m=10
M2 net2 INM net1 VSS nch_25ud18 l=800n w=9u m=10
M63 net057 net057 VDD VDD pch l=200n w=2.5u m=4
M114 VCMFB3 net057 VDD VDD pch l=200n w=2.5u m=4
M111 OUTP VBP VDD VDD pch l=800n w=10u m=40
M73 OUTM VCMFB3 VDD VDD pch l=800n w=10u m=40
M112 OUTP VCMFB3 VDD VDD pch l=800n w=10u m=40
M14 OUTM VBP VDD VDD pch l=800n w=10u m=40
M9 VOP2 VOM1 VDD VDD pch l=400n w=10u m=80
M7 net07 VCMFB1 VDD VDD pch l=800n w=10u m=4
M108 net08 VCMFB1 VDD VDD pch l=800n w=10u m=4
M6 VOM1 VBP1 net07 VDD pch l=200n w=5u m=10
M107 VOP1 VBP1 net08 VDD pch l=200n w=5u m=10
M109 VOM2 VOP1 VDD VDD pch l=400n w=10u m=80
M26 VBP1 VBP1 VDD VDD pch l=1.6u w=5u m=10
M90 VBP VBP VDD VDD pch l=800n w=10u m=4
C5 VOP2 OUTM VSS cfmom nr=88 lr=10u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C1 VOM2 OUTP VSS cfmom nr=88 lr=10u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C7 VOP1 OUTM VSS cfmom nr=50 lr=6u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C6 VOM1 OUTP VSS cfmom nr=50 lr=6u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
R4 VOP1 VCMFB1 VSS rppolywo_m lr=100.0000u wr=400n m=1
R6 VCMFB1 VOM1 VSS rppolywo_m lr=100.0000u wr=400n m=1
R9 OUTP net056 VSS rppolywo_m lr=8u wr=400n m=1
R10 net056 OUTM VSS rppolywo_m lr=8u wr=400n m=1
R7 VOP2 VCMFB2 VSS rppolywo_m lr=10u wr=400n m=1
R8 VCMFB2 VOM2 VSS rppolywo_m lr=10u wr=400n m=1
.ends