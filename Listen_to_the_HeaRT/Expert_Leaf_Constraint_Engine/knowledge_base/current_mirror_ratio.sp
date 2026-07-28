** Scaled Current Mirror (W*N/L ratio via nf or m)
** Pattern: Same W/L per finger, ratio achieved by different nf (or m).
** Here M0 has nf=2 (reference), M1 has nf=8 (4x output).
** Layout uses pattern='ratio_devices' (pattern 3) in align/primitive/main.py
** Works for any MOS type.

.subckt CURRENT_MIRROR_RATIO IREF IOUT S
M0 IREF IREF S S nmos_rvt w=1e-6 l=180n nf=2 m=1
M1 IOUT IREF S S nmos_rvt w=1e-6 l=180n nf=8 m=1
.ends CURRENT_MIRROR_RATIO
