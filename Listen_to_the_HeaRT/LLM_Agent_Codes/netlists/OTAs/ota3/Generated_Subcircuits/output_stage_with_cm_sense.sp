.subckt output_stage_with_cm_sense VOP2 VOM2 OUTM OUTP VBP VCMFB3 net056 VDD VSS
M13 OUTM VOP2 VSS VSS nch l=400n w=2.5u m=16
M113 OUTP VOM2 VSS VSS nch l=400n w=2.5u m=16
M111 OUTP VBP VDD VDD pch l=800n w=10u m=40
M14 OUTM VBP VDD VDD pch l=800n w=10u m=40
M112 OUTP VCMFB3 VDD VDD pch l=800n w=10u m=40
M73 OUTM VCMFB3 VDD VDD pch l=800n w=10u m=40
R9 OUTP net056 VSS rppolywo_m lr=8u wr=400n m=1
R10 net056 OUTM VSS rppolywo_m lr=8u wr=400n m=1
.ends output_stage_with_cm_sense