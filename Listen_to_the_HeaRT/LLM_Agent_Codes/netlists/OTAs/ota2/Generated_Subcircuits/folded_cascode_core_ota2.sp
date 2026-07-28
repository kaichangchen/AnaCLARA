.subckt folded_cascode_core_ota2 GND VDD VIP VIM VO1P VO1M IBIAS NBIAS_TAIL PCAS
M34 net0130 VIM PTAIL VDD pch_lvt l=240.0n w=3.6u m=24
M35 net0132 VIP PTAIL VDD pch_lvt l=240.0n w=3.6u m=24
M26 VO1M PCAS net0132 VDD pch_lvt l=240.0n w=4.8u m=26
M27 VO1P PCAS net0130 VDD pch_lvt l=240.0n w=4.8u m=26
M10 net0131 VIM NTAIL GND nch_lvt l=240.0n w=3.6u m=32
M8 net0133 VIP NTAIL GND nch_lvt l=240.0n w=3.6u m=32
M17 VO1M IBIAS net0133 GND nch_lvt l=240.0n w=3.6u m=33
M18 VO1P IBIAS net0131 GND nch_lvt l=240.0n w=3.6u m=33
M1 NTAIL NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=104
M74 PTAIL net0118 VDD VDD pch_lvt l=120.0n w=1.2u m=40
R12 net0118 VO1P rppolywo l=139.145u w=400n m=1
R5 VO1M net0118 rppolywo l=139.145u w=400n m=1
C1 VO1P net0118 GND cfmom nr=60 lr=8.2u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C0 net0118 VO1M GND cfmom nr=60 lr=8.2u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
.ends folded_cascode_core_ota2