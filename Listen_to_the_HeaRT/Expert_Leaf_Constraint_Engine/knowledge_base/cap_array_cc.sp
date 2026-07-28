** Common-Centroid Capacitor Array (DAC-style)
** Pattern: Multiple unit caps forming a weighted bank with common bottom plate.
** Binary-weighted example: 1C, 1C, 2C, 4C for a 3-bit DAC.
** GroupCaps constraint triggers common-centroid placement via cap_placer.
** Works with any cap model.

.subckt CAP_ARRAY_CC B0 B1 B2 VREF BOT
C0 B0 BOT capacitor c=100e-15
C1 B1 BOT capacitor c=100e-15
C2 B1 BOT capacitor c=100e-15
C3 B2 BOT capacitor c=100e-15
C4 B2 BOT capacitor c=100e-15
C5 B2 BOT capacitor c=100e-15
C6 B2 BOT capacitor c=100e-15
C7 VREF BOT capacitor c=100e-15
.ends CAP_ARRAY_CC
