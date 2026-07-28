.subckt complementary_differential_ota_core gnd ib_sink vdd vin vip vo
M2 net1 net2 gnd gnd nch l=ln_tail w=wn_tail m=1 nf=1
M1 vo vin net1 gnd nch l=ln_input w=wn_input m=1 nf=1
M0 net2 vip net1 gnd nch l=ln_input w=wn_input m=1 nf=1
M5 net3 ib_sink vdd vdd pch l=lp_tail w=wp_tail m=1 nf=1
M4 vo vin net3 vdd pch l=lp_input w=wp_input m=1 nf=1
M3 net2 vip net3 vdd pch l=lp_input w=wp_input m=1 nf=1
.ends complementary_differential_ota_core