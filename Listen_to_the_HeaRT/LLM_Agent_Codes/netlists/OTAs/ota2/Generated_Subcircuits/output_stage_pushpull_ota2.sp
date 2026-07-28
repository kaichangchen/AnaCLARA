.subckt output_stage_pushpull_ota2 GND VDD VIP VIM VO1P VO1M VOP VOM INCM2 vtail net0101
M70 VOM VO1P VDD VDD pch_lvt l=120.0n w=2.4u m=20
M71 VOP VO1M VDD VDD pch_lvt l=120.0n w=2.4u m=20
M12 VOP net096 vs GND nch_lvt l=120.0n w=3.6u m=30
M9 VOM net092 vs GND nch_lvt l=120.0n w=3.6u m=30
M50 vs vtail GND GND nch_hvt l=120.0n w=3.6u m=40
R11 net0101 VOM rppolywo l=21.6u w=400n m=1
R14 VOP net0101 rppolywo l=21.6u w=400n m=1
C4 net0101 VOP GND cfmom nr=32 lr=1.5u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C5 VOM net0101 GND cfmom nr=32 lr=1.5u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C6 VOM vtail GND cfmom nr=32 lr=2.7u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
C7 vtail VOP GND cfmom nr=32 lr=2.7u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n 
R0 net092 INCM2 rppolywo l=36.0u w=400n m=1
R13 net096 INCM2 rppolywo l=36.0u w=400n m=1
C2 VIP net092 GND cfmom nr=120 lr=18.0u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C3 VIM net096 GND cfmom nr=120 lr=18.0u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
.ends output_stage_pushpull_ota2