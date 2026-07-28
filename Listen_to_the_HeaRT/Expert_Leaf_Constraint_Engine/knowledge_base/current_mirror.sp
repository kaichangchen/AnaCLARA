** Simple Current Mirror (W/L matching)
** Pattern: Diode-connected reference + output device, same W/L.
** Works for any MOS type (nmos_rvt, pmos_rvt, etc.)
** Template match: SCM_NMOS / SCM_PMOS in align/config/basic_template.sp

.subckt CURRENT_MIRROR IREF IOUT S
M0 IREF IREF S S nmos_rvt w=1e-6 l=180n nf=4 m=1
M1 IOUT IREF S S nmos_rvt w=1e-6 l=180n nf=4 m=1
.ends CURRENT_MIRROR
