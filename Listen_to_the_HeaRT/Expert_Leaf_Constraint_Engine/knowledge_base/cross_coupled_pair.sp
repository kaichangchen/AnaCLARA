** Cross-Coupled Pair (latch half-circuit)
** Pattern: Two FETs with gate-drain cross-connection (M1.G=M2.D, M2.G=M1.D).
** Used in sense amplifiers, SRAMs, oscillators, latches.
** Works for any MOS type.
** Template match: CCP_NMOS / CCP_PMOS in align/config/basic_template.sp

.subckt CROSS_COUPLED_PAIR OUTP OUTN S
M1 OUTP OUTN S S nmos_rvt w=1e-6 l=90n nf=8 m=1
M2 OUTN OUTP S S nmos_rvt w=1e-6 l=90n nf=8 m=1
.ends CROSS_COUPLED_PAIR
