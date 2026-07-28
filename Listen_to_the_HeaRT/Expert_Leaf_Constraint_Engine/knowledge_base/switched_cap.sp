** Switched Capacitor Cell
** Pattern: A capacitor flanked by NMOS switches on each plate,
** driven by complementary clock phases.
** Template match: switched_capacitor_combination in align/config/user_template.sp

.subckt SWITCHED_CAP IN OUT CLK CLKB VSS
M1 IN CLK NET1 VSS nmos_rvt w=500n l=90n nf=2 m=1
C0 NET1 NET2 capacitor c=500e-15
M2 NET2 CLKB OUT VSS nmos_rvt w=500n l=90n nf=2 m=1
.ends SWITCHED_CAP
