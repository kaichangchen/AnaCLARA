** Transmission Gate (Pass Gate)
** Pattern: NMOS + PMOS in parallel with complementary clocks on gates.
** Source/drain nets are shared between the two devices.
** Template match: tgate in align/config/user_template.sp

.subckt TRANSMISSION_GATE IN OUT CLK CLKB VDD VSS
MN IN CLK OUT VSS nmos_rvt w=1e-6 l=90n nf=4 m=1
MP IN CLKB OUT VDD pmos_rvt w=2e-6 l=90n nf=4 m=1
.ends TRANSMISSION_GATE
