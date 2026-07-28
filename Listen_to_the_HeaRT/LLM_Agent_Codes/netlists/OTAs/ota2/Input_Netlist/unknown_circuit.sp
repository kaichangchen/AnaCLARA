.subckt ota2 GND IBIAS VCM VDD VIM VIP VOM VOP
M36 net0134 PCAS VDD VDD pch l=120.0n w=1.2u m=2
M32 net0136 net077 VDD VDD pch l=120.0n w=1.2u m=6
M33 net0138 net077 VDD VDD pch l=120.0n w=1.2u m=4
M24 net077 PCAS net0136 VDD pch_lvt l=120.0n w=1.2u m=6
M25 INCM2 PCAS net0138 VDD pch_lvt l=120.0n w=1.2u m=4
M28 PCAS PCAS net0134 VDD pch_lvt l=120.0n w=1.2u m=1
M26 VO1M PCAS net0132 VDD pch_lvt l=240.0n w=4.8u m=26
M27 VO1P PCAS net0130 VDD pch_lvt l=240.0n w=4.8u m=26
M68 vtail net0104 VDD VDD pch_lvt l=120.0n w=1.2u m=6
M69 net0104 net0104 VDD VDD pch_lvt l=120.0n w=1.2u m=6
M34 net0130 VIM PTAIL VDD pch_lvt l=240.0n w=3.6u m=24
M35 net0132 VIP PTAIL VDD pch_lvt l=240.0n w=3.6u m=24
M70 VOM VO1P VDD VDD pch_lvt l=120.0n w=2.4u m=20
M71 VOP VO1M VDD VDD pch_lvt l=120.0n w=2.4u m=20
M74 PTAIL net0118 VDD VDD pch_lvt l=120.0n w=1.2u m=40
C7 vtail VOP GND cfmom nr=32 lr=2.7u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C6 VOM vtail GND cfmom nr=32 lr=2.7u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C5 VOM net0101 GND cfmom nr=32 lr=1.5u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C4 net0101 VOP GND cfmom nr=32 lr=1.5u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C3 VIM net096 GND cfmom nr=120 lr=18.0u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C2 VIP net092 GND cfmom nr=120 lr=18.0u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C1 VO1P net0118 GND cfmom nr=60 lr=8.2u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C0 net0118 VO1M GND cfmom nr=60 lr=8.2u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
M2 VN1 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M4 VN2 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M3 net0135 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=5
M13 net077 VCM net0135 GND nch_lvt l=120.0n w=900n m=5
M14 INCM2 INCM2 net0137 GND nch_lvt l=240.0n w=600n m=2
M15 NBIAS_TAIL VCM VN2 GND nch_lvt l=120.0n w=900n m=13
M16 PCAS VCM VN1 GND nch_lvt l=120.0n w=900n m=13
M19 IBIAS IBIAS NBIAS_TAIL GND nch_lvt l=120.0n w=900n m=11
M1 NTAIL NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=104
M12 VOP net096 vs GND nch_lvt l=120.0n w=3.6u m=30
M9 VOM net092 vs GND nch_lvt l=120.0n w=3.6u m=30
M10 net0131 VIM NTAIL GND nch_lvt l=240.0n w=3.6u m=32
M8 net0133 VIP NTAIL GND nch_lvt l=240.0n w=3.6u m=32
M7 CMFBTAIL NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M17 VO1M IBIAS net0133 GND nch_lvt l=240.0n w=3.6u m=33
M18 VO1P IBIAS net0131 GND nch_lvt l=240.0n w=3.6u m=33
M20 vtail VCM CMFBTAIL GND nch_lvt l=120.0n w=900n m=6
M21 net0104 net0101 CMFBTAIL GND nch_lvt l=120.0n w=900n m=6
M6 net0137 INCM2 GND GND nch_hvt l=240.0n w=600n m=2
M50 vs vtail GND GND nch_hvt l=120.0n w=3.6u m=40
R0 net092 INCM2 rppolywo l=36.0u w=400n m=1
R13 net096 INCM2 rppolywo l=36.0u w=400n m=1
R12 net0118 VO1P rppolywo l=139.145u w=400n m=1
R5 VO1M net0118 rppolywo l=139.145u w=400n m=1
R14 VOP net0101 rppolywo l=21.6u w=400n m=1
R11 net0101 VOM rppolywo l=21.6u w=400n m=1
.ends 

