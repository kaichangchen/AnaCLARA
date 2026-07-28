.subckt cmfb3_error_amplifier net056 VREF VCMFB3 VBN VDD VSS
M63 net057 net057 VDD VDD pch l=200n w=2.5u m=4
M114 VCMFB3 net057 VDD VDD pch l=200n w=2.5u m=4
M60 net057 net056 net058 VSS nch l=200n w=2.2u m=4
M93 VCMFB3 VREF net058 VSS nch l=200n w=2.2u m=4
M105 net058 VBN VSS VSS nch l=400n w=11.0u m=8
.ends cmfb3_error_amplifier