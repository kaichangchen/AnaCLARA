** Matched Capacitor Pair
** Pattern: Two capacitors of equal value on symmetric signal paths.
** Used in differential filters, SC circuits, comparators.
** Works with any cap model (capacitor, nmoscap, CRTMOM, etc.)

.subckt CAP_MATCHED_PAIR INP INN BOT
C0 INP BOT capacitor c=1e-12
C1 INN BOT capacitor c=1e-12
.ends CAP_MATCHED_PAIR
