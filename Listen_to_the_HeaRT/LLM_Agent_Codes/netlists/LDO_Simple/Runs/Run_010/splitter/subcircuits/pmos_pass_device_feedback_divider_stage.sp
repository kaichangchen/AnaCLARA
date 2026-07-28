.subckt pmos_pass_device_feedback_divider_stage vdd gnd net2 vo fb
M0 vo net2 vdd vdd pmos l=l_power_p w=w_power_p*1 m=1 nf=1
R1 vo fb res r1
R2 fb gnd res r2
.ends pmos_pass_device_feedback_divider_stage