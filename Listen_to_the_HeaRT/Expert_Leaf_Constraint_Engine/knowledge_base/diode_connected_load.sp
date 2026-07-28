** Diode-Connected Load Pair
** Pattern: Two FETs with gate=drain acting as matched active loads.
** Typically used as load for a differential pair output.
** Works for any MOS type.
** Template match: DCL_NMOS / DCL_PMOS in align/config/basic_template.sp

.subckt DIODE_CONNECTED_LOAD OUTP OUTN VDD
M1 OUTP OUTP VDD VDD pmos_rvt w=2e-6 l=180n nf=8 m=1
M2 OUTN OUTN VDD VDD pmos_rvt w=2e-6 l=180n nf=8 m=1
.ends DIODE_CONNECTED_LOAD
