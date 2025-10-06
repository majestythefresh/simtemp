cd ../scripts 

# Build and load nxp driver for ARM64
./build.sh --driver "ARCH=arm64 CC=aarch64-linux-gnu-gcc"

# Build a python nxp command to run CLI
./build.sh --standalone

# Run CLI commands
nxp_simtemp get
nxp_simtemp set 30.5
nxp_simtemp trip set 0 50.0 THERMAL_TRIP_PASSIVE
nxp_simtemp trip set 1 62.0 THERMAL_TRIP_HOT
nxp_simtemp trip set 2 75.0 THERMAL_TRIP_CRITICAL
nxp_simtemp mode set ramp
nxp_simtemp sampling set 1000
nxp_simtemp monitoring start
nxp_simtemp stream