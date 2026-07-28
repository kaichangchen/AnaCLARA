.subckt output_cmfb_block_ota2 GND VDD NBIAS_TAIL VCM net0101 vtail
M68 vtail net0104 VDD VDD pch_lvt l=120.0n w=1.2u m=6
M69 net0104 net0104 VDD VDD pch_lvt l=120.0n w=1.2u m=6
M21 net0104 net0101 CMFBTAIL GND nch_lvt l=120.0n w=900n m=6
M20 vtail VCM CMFBTAIL GND nch_lvt l=120.0n w=900n m=6
M7 CMFBTAIL NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
.ends output_cmfb_block_ota2