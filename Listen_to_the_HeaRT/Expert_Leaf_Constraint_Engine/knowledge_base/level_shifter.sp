** Level Shifter Cell
** Pattern: Two matched FETs with split sources forming a symmetric
** level-shift buffer. Each device has a separate source node.
** Works for any MOS type.
** Template match: LS_S_NMOS_B / LS_S_PMOS_B in align/config/basic_template.sp

.subckt LEVEL_SHIFTER DA DB GA GB SA SB B
M1 DA GA SA B nmos_rvt w=1e-6 l=90n nf=4 m=1
M2 DB GB SB B nmos_rvt w=1e-6 l=90n nf=4 m=1
.ends LEVEL_SHIFTER
