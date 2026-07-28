.subckt first_stage_diffpair_active_load INM INP intp intm vbias_n vcmfb VBIAS_P VDD VSS
MP1b intp VBIAS_P VDD VDD pch l=120.0n w=2u m=20
MP1a intm VBIAS_P VDD VDD pch l=120.0n w=2u m=20
M10 net7 vbias_n VSS VSS nch_lvt l=120.0n w=2u m=16
M11 net7 vcmfb VSS VSS nch_lvt l=120.0n w=2u m=4
M0 intp INM net7 VSS nch_25ud18 l=500n w=5u m=12
M2 intm INP net7 VSS nch_25ud18 l=500n w=5u m=12
.ends first_stage_diffpair_active_load