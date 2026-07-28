.subckt cmfb_pmos_diffpair_amp OUTM OUTP VREF vcmfb VBIAS_P VDD VSS
M20 net028 VBIAS_P VDD VDD pch l=120.0n w=2u m=8
MP1c net020 VBIAS_P VDD VDD pch l=120.0n w=2u m=8
M18 vcmfb OUTM net028 VDD pch_lvt l=120.0n w=2u m=8
M15 vcmfb OUTP net020 VDD pch_lvt l=120.0n w=2u m=8
M19 net025 VREF net028 VDD pch_lvt l=120.0n w=2u m=8
M17 net025 VREF net020 VDD pch_lvt l=120.0n w=2u m=8
M13 vcmfb vcmfb VSS VSS nch_lvt l=120.0n w=2u m=2
M12 net025 net025 VSS VSS nch_lvt l=120.0n w=2u m=2
.ends cmfb_pmos_diffpair_amp