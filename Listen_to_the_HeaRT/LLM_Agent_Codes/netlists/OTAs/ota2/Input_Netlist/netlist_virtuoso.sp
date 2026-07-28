.subckt ota2 GND IBIAS VCM VDD VIM VIP VOM VOP
M0 net0134 PCAS VDD VDD pch_hvt l=120.0n w=1.2u m=2
M2 net0136 net077 VDD VDD pch l=120.0n w=1.2u m=6
M1 net0138 net077 VDD VDD pch l=120.0n w=1.2u m=4
M14 net077 PCAS net0136 VDD pch_lvt l=120.0n w=1.2u m=6
M13 INCM2 PCAS net0138 VDD pch_lvt l=120.0n w=1.2u m=4
M12 PCAS PCAS net0134 VDD pch_lvt l=120.0n w=1.2u m=1
M11 VO1M PCAS net0132 VDD pch_lvt l=240.0n w=4.8u m=26
M10 VO1P PCAS net0130 VDD pch_lvt l=240.0n w=4.8u m=26
M9 vtail net0104 VDD VDD pch_lvt l=120.0n w=1.2u m=6
M8 net0104 net0104 VDD VDD pch_lvt l=120.0n w=1.2u m=6
M7 net0130 VIM PTAIL VDD pch_lvt l=240.0n w=3.6u m=24
M6 net0132 VIP PTAIL VDD pch_lvt l=240.0n w=3.6u m=24
M5 VOM VO1P VDD VDD pch_lvt l=120.0n w=2.4u m=20
M4 VOP VO1M VDD VDD pch_lvt l=120.0n w=2.4u m=20
M3 PTAIL net0118 VDD VDD pch_lvt l=120.0n w=1.2u m=40
M34 VN1 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M33 VN2 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M32 net0135 NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=5
M31 net077 VCM net0135 GND nch_lvt l=120.0n w=900n m=5
M30 INCM2 INCM2 net0137 GND nch_lvt l=240.0n w=600n m=2
M29 NBIAS_TAIL VCM VN2 GND nch_lvt l=120.0n w=900n m=13
M28 PCAS VCM VN1 GND nch_lvt l=120.0n w=900n m=13
M27 IBIAS IBIAS NBIAS_TAIL GND nch_lvt l=120.0n w=900n m=11
M26 NTAIL NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=104
M25 VOP net096 vs GND nch_lvt l=120.0n w=3.6u m=30
M24 VOM net092 vs GND nch_lvt l=120.0n w=3.6u m=30
M23 net0131 VIM NTAIL GND nch_lvt l=240.0n w=3.6u m=32
M22 net0133 VIP NTAIL GND nch_lvt l=240.0n w=3.6u m=32
M21 CMFBTAIL NBIAS_TAIL GND GND nch_lvt l=120.0n w=900n m=13
M20 VO1M IBIAS net0133 GND nch_lvt l=240.0n w=3.6u m=33
M19 VO1P IBIAS net0131 GND nch_lvt l=240.0n w=3.6u m=33
M18 vtail VCM CMFBTAIL GND nch_lvt l=120.0n w=900n m=6
M17 net0104 net0101 CMFBTAIL GND nch_lvt l=120.0n w=900n m=6
M36 net0137 INCM2 GND GND nch_hvt l=240.0n w=600n m=2
M35 vs vtail GND GND nch_hvt l=120.0n w=3.6u m=40
C7 net0118 VO1M GND cfmom nr=60 lr=8.2u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C6 VO1P net0118 GND cfmom nr=60 lr=8.2u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C5 VIP net092 GND cfmom nr=120 lr=18.0u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C4 VIM net096 GND cfmom nr=120 lr=18.0u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C3 net0101 VOP GND cfmom nr=32 lr=1.5u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C2 VOM net0101 GND cfmom nr=32 lr=1.5u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C1 VOM vtail GND cfmom nr=32 lr=2.7u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C0 vtail VOP GND cfmom nr=32 lr=2.7u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
R5 net092 INCM2 rppolywo l=36.0u w=400n m=1
R4 net096 INCM2 rppolywo l=36.0u w=400n m=1
R3 net0118 VO1P rppolywo l=139.145u w=400n m=1
R2 VO1M net0118 rppolywo l=139.145u w=400n m=1
R1 VOP net0101 rppolywo l=21.6u w=400n m=1
R0 net0101 VOM rppolywo l=21.6u w=400n m=1
.ends