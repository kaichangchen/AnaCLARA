** Differential Pair
** Pattern: Two matched FETs sharing a source node, with a tail bias device.
** Works for any MOS type (nmos_rvt, pmos_rvt, nfet, pfet, NCH, PCH, etc.)
** Template match: DP_NMOS / DP_PMOS in align/config/basic_template.sp

.subckt DIFFERENTIAL_PAIR INP INN OUTP OUTN VB TAIL_S
M1 OUTP INP TAIL_S TAIL_S nmos_rvt w=1e-6 l=90n nf=10 m=1
M2 OUTN INN TAIL_S TAIL_S nmos_rvt w=1e-6 l=90n nf=10 m=1
M0 TAIL_S VB 0 0 nmos_rvt w=2e-6 l=180n nf=20 m=1
.ends DIFFERENTIAL_PAIR
