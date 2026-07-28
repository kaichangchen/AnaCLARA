.subckt bias_generator_block_ota3 VBN1 VBN VBP1 VBP VDD VSS
M26 VBP1 VBP1 VDD VDD pch l=1.6u w=5u m=10
M96 VBP1 VBN VSS VSS nch l=400n w=11.0u m=4
M90 VBP VBP VDD VDD pch l=800n w=10u m=4
M97 VBP VBN VSS VSS nch l=400n w=11.0u m=4
M21 VBN VBN VSS VSS nch l=400n w=11.0u m=4
M24 VBN1 VBN1 VBN VSS nch l=1u w=6u m=10
.ends bias_generator_block_ota3