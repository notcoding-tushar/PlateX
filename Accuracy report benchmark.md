# IITPAVE accuracy benchmark

The PlateX IRC:37 layered-elastic solver was compared with a recorded IITPAVE single-wheel run. The reference values are printed IITPAVE results from the controlled three-layer case in [IITPAVE comparison report](IITPAVE%20comparison%20report.md), section 2.4.

The section has 100 mm at 2000 MPa, 300 mm at 200 MPa and a 75 MPa half-space. All Poisson ratios are 0.3. A 20 kN circular wheel at 0.56 MPa is evaluated at 155 mm radial distance and 400 mm depth, at the interface between the base and subgrade. PlateX uses a bonded interface. IITPAVE values are rounded to their printed precision.

| Response | Interface side | IITPAVE | PlateX | Absolute relative difference |
|---|---|---:|---:|---:|
| Vertical stress (kPa) | Above | -21.960 | -21.9856 | 0.117% |
| Hoop stress (kPa) | Above | 23.410 | 23.4379 | 0.119% |
| Vertical displacement (mm) | Above | 0.1962 | 0.196505 | 0.156% |
| Vertical strain | Above | -0.0001734 | -0.000173581 | 0.105% |
| Vertical strain | Below | -0.0003093 | -0.000309683 | 0.124% |

The existing regression test in [test_layered_elastic_irc37.py](backend/tests/test_layered_elastic_irc37.py) checks these five values within 0.3%. This is one comparative case, with reference precision limited by the printed output. It does not establish accuracy for every layer configuration or validate the finite HOSNT12 solver against IITPAVE. The earlier investigation documented a seven-layer interface discrepancy in IITPAVE output that remains unresolved.
