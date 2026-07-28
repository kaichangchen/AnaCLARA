.subckt cross_coupled_compensation_network VOP2 VOM2 OUTM OUTP VOP1 VOM1 VSS
C5 VOP2 OUTM VSS cfmom nr=88 lr=10u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C1 VOM2 OUTP VSS cfmom nr=88 lr=10u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C7 VOP1 OUTM VSS cfmom nr=50 lr=6u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
C6 VOM1 OUTP VSS cfmom nr=50 lr=6u w=70n s=70n stm=1 spm=6 m=1 ftip=140.0n
.ends cross_coupled_compensation_network