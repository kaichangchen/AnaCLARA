.subckt bias_generator_block_ota2 GND VDD IBIAS VCM NBIAS_TAIL PCAS INCM2
M36 net0134 PCAS VDD VDD pch_hvt l=120.0n w=1.2u m=2
M32 net0136 net077 VDD VDD pch l=120.0n w=1.2u m=6
M33 net0138 net077 VDD VDD pch l=120.0n w=1.2u m=4
M24 net077 PCAS net0136 VDD pch_lvt l=120.0n w=1.2u m=6
M25 INCM2 PCAS net0138 VDD pch_lvt l=120.0n w=1.2u m=4
M28 PCAS PCAS net0134 VDD pch_lvt l=120.0n w=1.2u m=1
M2 VN1 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M4 VN2 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M3 net0135 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=5
M13 net077 VCM net0135 GND nch_lvt l=120.0n w=900n m=5
M14 INCM2 INCM2 net0137 GND nch_lvt l=240.0n w=600n m=2
M15 NBIAS_TAIL VCM VN2 GND nch_lvt l=120.0n w=900n m=13
M16 PCAS VCM VN1 GND nch_lvt l=120.0n w=900n m=13
M19 IBIAS IBIAS NBIAS_TAIL GND nch_lvt l=120.0n w=900n m=11
M6 net0137 INCM2 GND GND nch_hvt l=240.0n w=600n m=2
.ends bias_generator_block_ota2