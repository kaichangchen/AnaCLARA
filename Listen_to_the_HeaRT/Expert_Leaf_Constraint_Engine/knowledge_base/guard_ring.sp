** Guard Ring
** Pattern: A sensitive subcircuit wrapped by a substrate/well guard ring.
** No automatic detection -- user must specify via GuardRing constraint.
** Guard ring generation: align/primitive/main.py generate_Ring
** C++ implementation: PlaceRouteHierFlow/guard_ring/

.subckt GUARD_RING_EXAMPLE INP INN OUTP OUTN VB VDD VSS
** Sensitive differential pair inside guard ring
M1 OUTP INP TAIL TAIL nmos_rvt w=1e-6 l=90n nf=10 m=1
M2 OUTN INN TAIL TAIL nmos_rvt w=1e-6 l=90n nf=10 m=1
M0 TAIL VB VSS VSS nmos_rvt w=2e-6 l=180n nf=20 m=1
.ends GUARD_RING_EXAMPLE
