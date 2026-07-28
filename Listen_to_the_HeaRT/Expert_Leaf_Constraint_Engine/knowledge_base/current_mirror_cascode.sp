** Cascode Current Mirror
** Pattern: Bottom mirror pair (M0,M1) + cascode pair (M2,M3) stacked above.
** Works for any MOS type. Drain of bottom pair connects to source of top pair.
** Template match: CASCODED_SCM_NMOS / CASCODED_SCM_PMOS in align/config/user_template.sp

.subckt CURRENT_MIRROR_CASCODE IREF IOUT VBC S
M0 NET1 IREF S S nmos_rvt w=1e-6 l=180n nf=4 m=1
M1 NET2 IREF S S nmos_rvt w=1e-6 l=180n nf=4 m=1
M2 IREF VBC NET1 S nmos_rvt w=1e-6 l=180n nf=4 m=1
M3 IOUT VBC NET2 S nmos_rvt w=1e-6 l=180n nf=4 m=1
.ends CURRENT_MIRROR_CASCODE
