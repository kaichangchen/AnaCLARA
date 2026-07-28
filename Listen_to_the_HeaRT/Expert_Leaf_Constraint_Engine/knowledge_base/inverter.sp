** CMOS Inverter
** Pattern: One NMOS + one PMOS with shared gate (input) and shared drain (output).
** Template match: INV / INV_B in align/config/user_template.sp

.subckt INVERTER IN OUT VDD VSS
MP OUT IN VDD VDD pmos_rvt w=2e-6 l=90n nf=4 m=1
MN OUT IN VSS VSS nmos_rvt w=1e-6 l=90n nf=4 m=1
.ends INVERTER
