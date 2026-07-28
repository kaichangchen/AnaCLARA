.subckt second_stage_current_mirror_gain VOP1 VOM1 VOP2 VOM2 VBN VDD VSS
M9 VOP2 VOM1 VDD VDD pch l=400n w=10u m=80
M109 VOM2 VOP1 VDD VDD pch l=400n w=10u m=80
M18 VOP2 VBN VSS VSS nch l=400n w=11.0u m=4
M102 VOM2 VBN VSS VSS nch l=400n w=11.0u m=4
M75 VOP2 VCMFB2 VSS VSS nch l=400n w=2.5u m=8
M110 VOM2 VCMFB2 VSS VSS nch l=400n w=2.5u m=8
R7 VOP2 VCMFB2 VSS rppolywo_m lr=10u wr=400n m=1
R8 VCMFB2 VOM2 VSS rppolywo_m lr=10u wr=400n m=1
.ends second_stage_current_mirror_gain