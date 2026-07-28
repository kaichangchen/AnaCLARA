.subckt first_stage_telescopic_diffpair INM INP VOP1 VOM1 VBN1 VBP1 VBN VDD VSS
M106 VOP1 VBN1 net2 VSS nch l=200n w=6u m=10
M3 VOM1 VBN1 net4 VSS nch l=200n w=6u m=10
M4 net1 VBN VSS VSS nch l=400n w=11.0u m=28
M12 net4 INP net1 VSS nch_25ud18 l=800n w=9u m=10
M2 net2 INM net1 VSS nch_25ud18 l=800n w=9u m=10
M7 net07 VCMFB1 VDD VDD pch l=800n w=10u m=4
M108 net08 VCMFB1 VDD VDD pch l=800n w=10u m=4
M6 VOM1 VBP1 net07 VDD pch l=200n w=5u m=10
M107 VOP1 VBP1 net08 VDD pch l=200n w=5u m=10
R4 VOP1 VCMFB1 VSS rppolywo_m lr=100.0000u wr=400n m=1
R6 VCMFB1 VOM1 VSS rppolywo_m lr=100.0000u wr=400n m=1
.ends first_stage_telescopic_diffpair