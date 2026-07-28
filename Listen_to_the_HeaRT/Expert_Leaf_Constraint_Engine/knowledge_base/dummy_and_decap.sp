** Dummy Devices and Decap Cells (informational)
** Pattern: Dummy FET with all terminals tied or gate tied to supply.
** Decap: MOS capacitor with gate as one plate.
** Template match: DUMMY_NMOS / DCAP_NMOS in align/config/basic_template.sp
** Auto-detected by remove_dummy_devices in align/compiler/preprocess.py

.subckt DUMMY_AND_DECAP VDD VSS
** Dummy: gate=source=drain=body (non-functional, for matching/fill)
MDUMMY VSS VSS VSS VSS nmos_rvt w=1e-6 l=90n nf=2 m=1
** Decap: gate-to-source MOS capacitor (power supply decoupling)
MDECAP VSS VDD VSS VSS nmos_rvt w=2e-6 l=180n nf=10 m=1
.ends DUMMY_AND_DECAP
