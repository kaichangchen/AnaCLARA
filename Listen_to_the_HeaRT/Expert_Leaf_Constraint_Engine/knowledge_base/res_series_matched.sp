** Matched Resistors in Series
** Pattern: Multiple resistors of same value chained in series.
** Constraint ensures identical layout cells placed in a row.
** Works with any resistor model (resistor, rppolywo, etc.)

.subckt RES_SERIES_MATCHED INP OUTN
R0 INP NET1 resistor r=1000
R1 NET1 NET2 resistor r=1000
R2 NET2 OUTN resistor r=1000
.ends RES_SERIES_MATCHED
