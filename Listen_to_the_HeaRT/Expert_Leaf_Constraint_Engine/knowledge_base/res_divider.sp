** Resistive Voltage Divider
** Pattern: Two resistors in series between two nodes with a midpoint tap.
** If same value: 1:1 divider. Different values: ratio divider.
** Works with any resistor model (resistor, rppolywo, etc.)

.subckt RES_DIVIDER VIN VMID VOUT
R0 VIN VMID resistor r=10000
R1 VMID VOUT resistor r=10000
.ends RES_DIVIDER
