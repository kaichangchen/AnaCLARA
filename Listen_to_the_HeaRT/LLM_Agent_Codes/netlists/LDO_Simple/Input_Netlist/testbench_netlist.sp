// Generated for: spectre
// Generated on: Feb 13 19:08:38 2026
// Design library name: iclad_40n_SP
// Design cell name: test_ldo
// Design view name: schematic
simulator lang=spectre
global 0
parameters vref=0.8 vdd=1.8 ib=100n rl=10M cl=50f rz=1K rd=600K l_cs_p=2u \
    l_eab_p=500n l_eai_p=500n l_eal_n=500n l_power_p=500n lcc=10u n_rd=1 \
    n_rz=1 w_cs_p=4u w_eab_p=4u w_eai_p=4u w_eal_n=2u w_power_p=100u \
    wcc=10u
include "/usr/local/packages/tsmc_40/pdk/tsmcN40/../models/spectre/toplevel.scs" section=top_tt

// Library name: src_40n
// Cell name: ldo_pmos_v1_auto
// View name: schematic
subckt ldo_pmos_v1_auto fb fbr gnd iref_snk vdd vin vo
    M6 (gnd net7 net2 vdd) pch_25 l=l_eab_p w=w_eab_p*1 m=1 nf=1 sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_eab_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_eab_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eab_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_eab_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eab_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_eab_p) \
        nrd=0 nrs=0
    M5 (net2 iref_snk vdd vdd) pch_25 l=l_cs_p w=w_cs_p*1 m=1 nf=1 \
        sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_cs_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_cs_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_cs_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_cs_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_cs_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_cs_p) \
        nrd=0 nrs=0
    M4 (net7 vin net5 vdd) pch_25 l=l_eai_p w=w_eai_p*1 m=1 nf=1 sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_eai_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_eai_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eai_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_eai_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eai_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_eai_p) \
        nrd=0 nrs=0
    M3 (net6 fb net5 vdd) pch_25 l=l_eai_p w=w_eai_p*1 m=1 nf=1 sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_eai_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_eai_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eai_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_eai_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eai_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_eai_p) \
        nrd=0 nrs=0
    M2 (net5 iref_snk vdd vdd) pch_25 l=l_cs_p w=w_cs_p*1 m=1 nf=1 \
        sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_cs_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_cs_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_cs_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_cs_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_cs_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_cs_p) \
        nrd=0 nrs=0
    M1 (iref_snk iref_snk vdd vdd) pch_25 l=l_cs_p w=w_cs_p*1 m=1 nf=1 \
        sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_cs_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_cs_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_cs_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_cs_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_cs_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_cs_p) \
        nrd=0 nrs=0
    M0 (vo net2 vdd vdd) pch_25 l=l_power_p w=w_power_p*1 m=1 nf=1 \
        sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_power_p \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_power_p \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_power_p)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_power_p) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_power_p)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_power_p) \
        nrd=0 nrs=0
//Series configuration of R2
R2_1__dmy0  (net1 R2_1__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_2__dmy0  (R2_1__dmy0 R2_2__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_3__dmy0  (R2_2__dmy0 R2_3__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_4__dmy0  (R2_3__dmy0 R2_4__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_5__dmy0  (R2_4__dmy0 R2_5__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_6__dmy0  (R2_5__dmy0 R2_6__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_7__dmy0  (R2_6__dmy0 R2_7__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_8__dmy0  (R2_7__dmy0 R2_8__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_9__dmy0  (R2_8__dmy0 R2_9__dmy0 ) rppolywo l=1u w=1u m=1 multi=(1)
R2_10__dmy0  (R2_9__dmy0 vo ) rppolywo l=1u w=1u m=1 multi=(1)
//End of R2

//Series configuration of R1
R1_1__dmy0  (fbr R1_1__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_2__dmy0  (R1_1__dmy0 R1_2__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_3__dmy0  (R1_2__dmy0 R1_3__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_4__dmy0  (R1_3__dmy0 R1_4__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_5__dmy0  (R1_4__dmy0 R1_5__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_6__dmy0  (R1_5__dmy0 R1_6__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_7__dmy0  (R1_6__dmy0 R1_7__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_8__dmy0  (R1_7__dmy0 R1_8__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_9__dmy0  (R1_8__dmy0 R1_9__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_10__dmy0  (R1_9__dmy0 R1_10__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_11__dmy0  (R1_10__dmy0 R1_11__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_12__dmy0  (R1_11__dmy0 R1_12__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_13__dmy0  (R1_12__dmy0 R1_13__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_14__dmy0  (R1_13__dmy0 R1_14__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_15__dmy0  (R1_14__dmy0 R1_15__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_16__dmy0  (R1_15__dmy0 R1_16__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_17__dmy0  (R1_16__dmy0 R1_17__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_18__dmy0  (R1_17__dmy0 R1_18__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_19__dmy0  (R1_18__dmy0 R1_19__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_20__dmy0  (R1_19__dmy0 R1_20__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_21__dmy0  (R1_20__dmy0 R1_21__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_22__dmy0  (R1_21__dmy0 R1_22__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_23__dmy0  (R1_22__dmy0 R1_23__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_24__dmy0  (R1_23__dmy0 R1_24__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_25__dmy0  (R1_24__dmy0 R1_25__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_26__dmy0  (R1_25__dmy0 R1_26__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_27__dmy0  (R1_26__dmy0 R1_27__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_28__dmy0  (R1_27__dmy0 R1_28__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_29__dmy0  (R1_28__dmy0 R1_29__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_30__dmy0  (R1_29__dmy0 R1_30__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_31__dmy0  (R1_30__dmy0 R1_31__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_32__dmy0  (R1_31__dmy0 R1_32__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_33__dmy0  (R1_32__dmy0 R1_33__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_34__dmy0  (R1_33__dmy0 R1_34__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_35__dmy0  (R1_34__dmy0 R1_35__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_36__dmy0  (R1_35__dmy0 R1_36__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_37__dmy0  (R1_36__dmy0 R1_37__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_38__dmy0  (R1_37__dmy0 R1_38__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_39__dmy0  (R1_38__dmy0 R1_39__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_40__dmy0  (R1_39__dmy0 R1_40__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_41__dmy0  (R1_40__dmy0 R1_41__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_42__dmy0  (R1_41__dmy0 R1_42__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_43__dmy0  (R1_42__dmy0 R1_43__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_44__dmy0  (R1_43__dmy0 R1_44__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_45__dmy0  (R1_44__dmy0 R1_45__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_46__dmy0  (R1_45__dmy0 R1_46__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_47__dmy0  (R1_46__dmy0 R1_47__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_48__dmy0  (R1_47__dmy0 R1_48__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_49__dmy0  (R1_48__dmy0 R1_49__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_50__dmy0  (R1_49__dmy0 R1_50__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_51__dmy0  (R1_50__dmy0 R1_51__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_52__dmy0  (R1_51__dmy0 R1_52__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_53__dmy0  (R1_52__dmy0 R1_53__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_54__dmy0  (R1_53__dmy0 R1_54__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_55__dmy0  (R1_54__dmy0 R1_55__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_56__dmy0  (R1_55__dmy0 R1_56__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_57__dmy0  (R1_56__dmy0 R1_57__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_58__dmy0  (R1_57__dmy0 R1_58__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_59__dmy0  (R1_58__dmy0 R1_59__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_60__dmy0  (R1_59__dmy0 R1_60__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_61__dmy0  (R1_60__dmy0 R1_61__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_62__dmy0  (R1_61__dmy0 R1_62__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_63__dmy0  (R1_62__dmy0 R1_63__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_64__dmy0  (R1_63__dmy0 R1_64__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_65__dmy0  (R1_64__dmy0 R1_65__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_66__dmy0  (R1_65__dmy0 R1_66__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_67__dmy0  (R1_66__dmy0 R1_67__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_68__dmy0  (R1_67__dmy0 R1_68__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_69__dmy0  (R1_68__dmy0 R1_69__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_70__dmy0  (R1_69__dmy0 R1_70__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_71__dmy0  (R1_70__dmy0 R1_71__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_72__dmy0  (R1_71__dmy0 R1_72__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_73__dmy0  (R1_72__dmy0 R1_73__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_74__dmy0  (R1_73__dmy0 R1_74__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_75__dmy0  (R1_74__dmy0 R1_75__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_76__dmy0  (R1_75__dmy0 R1_76__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_77__dmy0  (R1_76__dmy0 R1_77__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_78__dmy0  (R1_77__dmy0 R1_78__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_79__dmy0  (R1_78__dmy0 R1_79__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_80__dmy0  (R1_79__dmy0 R1_80__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_81__dmy0  (R1_80__dmy0 R1_81__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_82__dmy0  (R1_81__dmy0 R1_82__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_83__dmy0  (R1_82__dmy0 R1_83__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_84__dmy0  (R1_83__dmy0 R1_84__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_85__dmy0  (R1_84__dmy0 R1_85__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_86__dmy0  (R1_85__dmy0 R1_86__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_87__dmy0  (R1_86__dmy0 R1_87__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_88__dmy0  (R1_87__dmy0 R1_88__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_89__dmy0  (R1_88__dmy0 R1_89__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_90__dmy0  (R1_89__dmy0 R1_90__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_91__dmy0  (R1_90__dmy0 R1_91__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_92__dmy0  (R1_91__dmy0 R1_92__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_93__dmy0  (R1_92__dmy0 R1_93__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_94__dmy0  (R1_93__dmy0 R1_94__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_95__dmy0  (R1_94__dmy0 R1_95__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_96__dmy0  (R1_95__dmy0 R1_96__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_97__dmy0  (R1_96__dmy0 R1_97__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_98__dmy0  (R1_97__dmy0 R1_98__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_99__dmy0  (R1_98__dmy0 R1_99__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R1_100__dmy0  (R1_99__dmy0 gnd ) rppolywo l=10u w=1u m=1 multi=(1)
//End of R1

//Series configuration of R0
R0_1__dmy0  (vo R0_1__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_2__dmy0  (R0_1__dmy0 R0_2__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_3__dmy0  (R0_2__dmy0 R0_3__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_4__dmy0  (R0_3__dmy0 R0_4__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_5__dmy0  (R0_4__dmy0 R0_5__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_6__dmy0  (R0_5__dmy0 R0_6__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_7__dmy0  (R0_6__dmy0 R0_7__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_8__dmy0  (R0_7__dmy0 R0_8__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_9__dmy0  (R0_8__dmy0 R0_9__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_10__dmy0  (R0_9__dmy0 R0_10__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_11__dmy0  (R0_10__dmy0 R0_11__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_12__dmy0  (R0_11__dmy0 R0_12__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_13__dmy0  (R0_12__dmy0 R0_13__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_14__dmy0  (R0_13__dmy0 R0_14__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_15__dmy0  (R0_14__dmy0 R0_15__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_16__dmy0  (R0_15__dmy0 R0_16__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_17__dmy0  (R0_16__dmy0 R0_17__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_18__dmy0  (R0_17__dmy0 R0_18__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_19__dmy0  (R0_18__dmy0 R0_19__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_20__dmy0  (R0_19__dmy0 R0_20__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_21__dmy0  (R0_20__dmy0 R0_21__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_22__dmy0  (R0_21__dmy0 R0_22__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_23__dmy0  (R0_22__dmy0 R0_23__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_24__dmy0  (R0_23__dmy0 R0_24__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_25__dmy0  (R0_24__dmy0 R0_25__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_26__dmy0  (R0_25__dmy0 R0_26__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_27__dmy0  (R0_26__dmy0 R0_27__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_28__dmy0  (R0_27__dmy0 R0_28__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_29__dmy0  (R0_28__dmy0 R0_29__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_30__dmy0  (R0_29__dmy0 R0_30__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_31__dmy0  (R0_30__dmy0 R0_31__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_32__dmy0  (R0_31__dmy0 R0_32__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_33__dmy0  (R0_32__dmy0 R0_33__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_34__dmy0  (R0_33__dmy0 R0_34__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_35__dmy0  (R0_34__dmy0 R0_35__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_36__dmy0  (R0_35__dmy0 R0_36__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_37__dmy0  (R0_36__dmy0 R0_37__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_38__dmy0  (R0_37__dmy0 R0_38__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_39__dmy0  (R0_38__dmy0 R0_39__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_40__dmy0  (R0_39__dmy0 R0_40__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_41__dmy0  (R0_40__dmy0 R0_41__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_42__dmy0  (R0_41__dmy0 R0_42__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_43__dmy0  (R0_42__dmy0 R0_43__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_44__dmy0  (R0_43__dmy0 R0_44__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_45__dmy0  (R0_44__dmy0 R0_45__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_46__dmy0  (R0_45__dmy0 R0_46__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_47__dmy0  (R0_46__dmy0 R0_47__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_48__dmy0  (R0_47__dmy0 R0_48__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_49__dmy0  (R0_48__dmy0 R0_49__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_50__dmy0  (R0_49__dmy0 R0_50__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_51__dmy0  (R0_50__dmy0 R0_51__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_52__dmy0  (R0_51__dmy0 R0_52__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_53__dmy0  (R0_52__dmy0 R0_53__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_54__dmy0  (R0_53__dmy0 R0_54__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_55__dmy0  (R0_54__dmy0 R0_55__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_56__dmy0  (R0_55__dmy0 R0_56__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_57__dmy0  (R0_56__dmy0 R0_57__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_58__dmy0  (R0_57__dmy0 R0_58__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_59__dmy0  (R0_58__dmy0 R0_59__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_60__dmy0  (R0_59__dmy0 R0_60__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_61__dmy0  (R0_60__dmy0 R0_61__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_62__dmy0  (R0_61__dmy0 R0_62__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_63__dmy0  (R0_62__dmy0 R0_63__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_64__dmy0  (R0_63__dmy0 R0_64__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_65__dmy0  (R0_64__dmy0 R0_65__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_66__dmy0  (R0_65__dmy0 R0_66__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_67__dmy0  (R0_66__dmy0 R0_67__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_68__dmy0  (R0_67__dmy0 R0_68__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_69__dmy0  (R0_68__dmy0 R0_69__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_70__dmy0  (R0_69__dmy0 R0_70__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_71__dmy0  (R0_70__dmy0 R0_71__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_72__dmy0  (R0_71__dmy0 R0_72__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_73__dmy0  (R0_72__dmy0 R0_73__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_74__dmy0  (R0_73__dmy0 R0_74__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_75__dmy0  (R0_74__dmy0 R0_75__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_76__dmy0  (R0_75__dmy0 R0_76__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_77__dmy0  (R0_76__dmy0 R0_77__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_78__dmy0  (R0_77__dmy0 R0_78__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_79__dmy0  (R0_78__dmy0 R0_79__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_80__dmy0  (R0_79__dmy0 R0_80__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_81__dmy0  (R0_80__dmy0 R0_81__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_82__dmy0  (R0_81__dmy0 R0_82__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_83__dmy0  (R0_82__dmy0 R0_83__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_84__dmy0  (R0_83__dmy0 R0_84__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_85__dmy0  (R0_84__dmy0 R0_85__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_86__dmy0  (R0_85__dmy0 R0_86__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_87__dmy0  (R0_86__dmy0 R0_87__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_88__dmy0  (R0_87__dmy0 R0_88__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_89__dmy0  (R0_88__dmy0 R0_89__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_90__dmy0  (R0_89__dmy0 R0_90__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_91__dmy0  (R0_90__dmy0 R0_91__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_92__dmy0  (R0_91__dmy0 R0_92__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_93__dmy0  (R0_92__dmy0 R0_93__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_94__dmy0  (R0_93__dmy0 R0_94__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_95__dmy0  (R0_94__dmy0 R0_95__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_96__dmy0  (R0_95__dmy0 R0_96__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_97__dmy0  (R0_96__dmy0 R0_97__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_98__dmy0  (R0_97__dmy0 R0_98__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_99__dmy0  (R0_98__dmy0 R0_99__dmy0 ) rppolywo l=10u w=1u m=1 multi=(1)
R0_100__dmy0  (R0_99__dmy0 fbr ) rppolywo l=10u w=1u m=1 multi=(1)
//End of R0

    M8 (net6 net6 gnd gnd) nch_25 l=l_eal_n w=w_eal_n*1 m=1 nf=1 sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_eal_n \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_eal_n \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eal_n)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_eal_n) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eal_n)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_eal_n) \
        nrd=0 nrs=0
    M7 (net7 net6 gnd gnd) nch_25 l=l_eal_n w=w_eal_n*1 m=1 nf=1 sd=220.0n \
        ad=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*((1/2)*2.2e-07))*w_eal_n \
        as=((1-int(1/2)*2)*(1.5e-07+((1-1)*2.2e-07)/2+0)+(1+1-int((1+1)/2)*2)*(1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0))*w_eal_n \
        pd=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eal_n)+(1+1-int((1+1)/2)*2)*(((1/2)*2.2e-07)*2+1*w_eal_n) \
        ps=(1-int(1/2)*2)*((1.5e-07+((1-1)*2.2e-07)/2+0)*2+(1+1)*w_eal_n)+(1+1-int((1+1)/2)*2)*((1.5e-07+1.5e-07+(1/2-1)*2.2e-07+0+0)*2+(1+2)*w_eal_n) \
        nrd=0 nrs=0
    C0 (net7 net1) nmoscap lr=wcc wr=lcc multi=1
ends ldo_pmos_v1_auto
// End of subcircuit definition.

// Library name: iclad_40n_SP
// Cell name: test_ldo
// View name: schematic
V2 (VREF GND) vsource dc=vref type=dc
V1 (GND 0) vsource dc=0 type=dc
V0 (VDD GND) vsource dc=vdd mag=1 type=dc
I1 (ib GND) isource dc=ib type=dc
R1 (vo net1) resistor r=100.0m
R0 (vo GND) resistor r=rl
C0 (net1 GND) capacitor c=cl
IPRB0 (net3 fb) iprobe
I2 (fb net3 GND ib VDD VREF vo) ldo_pmos_v1_auto
simulatorOptions options psfversion="1.4.0" reltol=1e-3 vabstol=1e-6 \
    iabstol=1e-12 temp=27 tnom=27 scalem=1.0 scale=1.0 gmin=1e-12 rforce=1 \
    maxnotes=5 maxwarns=5 digits=5 cols=80 pivrel=1e-3 \
    sensfile="../psf/sens.output" checklimitdest=psf 
dcOp dc write="spectre.dc" maxiters=150 maxsteps=10000 annotate=status
dcOpInfo info what=oppoint where=rawfile
ac ac start=0.1 stop=10G dec=10 annotate=status 
stb stb start=0.1 stop=10G dec=10 probe=IPRB0 localgnd=GND annotate=status 
modelParameter info what=models where=rawfile
element info what=inst where=rawfile
outputParameter info what=output where=rawfile
designParamVals info what=parameters where=rawfile
primitives info what=primitives where=rawfile
subckts info what=subckts where=rawfile
save I2:5 R0:1 
saveOptions options save=allpub
