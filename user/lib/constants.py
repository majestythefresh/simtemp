"""
Constants and enumerations for NXP Simulated Temperature Sensor.

This module defines all constants, enumerations, and data structures used for
communication with the NXP Simulated Temperature Sensor driver via IOCTL commands
and binary data formats.
"""

import struct
from enum import IntEnum


class NXPIoctl(IntEnum):
    """
    IOCTL command definitions for NXP Simulated Temperature Sensor.

    These constants define the IOCTL commands used to communicate with the
    simulated temperature sensor driver. Each command follows the standard
    Linux IOCTL encoding format.
    """

    # Set current temperature: _IOW('T', 1, int)
    NXP_SIMTEMP_SET_TEMP = 0x40045401

    # Get current temperature: _IOR('T', 2, int)
    NXP_SIMTEMP_GET_TEMP = 0x80045402

    # Set trip point: _IOW('T', 3, int[3])
    NXP_SIMTEMP_SET_TRIP = 0x400C5403

    # Get trip point: _IOR('T', 4, int[3])
    NXP_SIMTEMP_GET_TRIP = 0x800C5404

    # Start temperature monitoring: _IO('T', 5)
    NXP_SIMTEMP_START_MONITOR = 0x00005405

    # Stop temperature monitoring: _IO('T', 6)
    NXP_SIMTEMP_STOP_MONITOR = 0x00005406


class TripType:
    """
    Trip type definitions for NXP Simulated Temperature Sensor.

    This class defines the different types of thermal trip points supported
    by the driver, along with mapping between numeric values and string names.
    """

    # Active cooling trip - triggers active cooling mechanisms
    THERMAL_TRIP_ACTIVE = 0

    # Passive cooling trip - triggers passive cooling mechanisms
    THERMAL_TRIP_PASSIVE = 1

    # Hot trip - indicates hot but not critical temperature
    THERMAL_TRIP_HOT = 2

    # Critical trip - indicates critical temperature requiring immediate action
    THERMAL_TRIP_CRITICAL = 3

    # Mapping from string names to numeric values
    NAME = {
        "THERMAL_TRIP_ACTIVE": THERMAL_TRIP_ACTIVE,
        "THERMAL_TRIP_PASSIVE": THERMAL_TRIP_PASSIVE,
        "THERMAL_TRIP_HOT": THERMAL_TRIP_HOT,
        "THERMAL_TRIP_CRITICAL": THERMAL_TRIP_CRITICAL,
    }

    # Mapping from numeric values to string names
    TYPE = {
        THERMAL_TRIP_ACTIVE: "THERMAL_TRIP_ACTIVE",
        THERMAL_TRIP_PASSIVE: "THERMAL_TRIP_PASSIVE",
        THERMAL_TRIP_HOT: "THERMAL_TRIP_HOT",
        THERMAL_TRIP_CRITICAL: "THERMAL_TRIP_CRITICAL",
    }


class OperationMode:
    """
    Operation mode definitions for NXP Simulated Temperature Sensor.

    This class defines the different operational modes of the simulated
    temperature sensor, each providing different temperature behavior patterns.
    """

    # Normal mode: provides small, predictable temperature variations
    MODE_NORMAL = "normal"

    # Noisy mode: adds random noise to temperature readings
    MODE_NOISY = "noisy"

    # Ramp mode: continuously ramps temperature up and down between limits
    MODE_RAMP = "ramp"

    # List of all valid operation modes
    VALID_MODES = [MODE_NORMAL, MODE_NOISY, MODE_RAMP]

    # Human-readable descriptions for each operation mode
    DESCRIPTION = {
        MODE_NORMAL: "Normal mode: small predictable temperature variations",
        MODE_NOISY: "Noisy mode: random noise added to temperature",
        MODE_RAMP: "Ramp mode: continuous ramp up and down between temperature limits",
    }


# Binary sample structure format string
# Format: 'Qii' represents:
#   Q: uint64_t (8 bytes) - timestamp in nanoseconds
#   i: int32_t (4 bytes)  - temperature in millidegrees Celsius
#   i: uint32_t (4 bytes) - flags and status bits
SAMPLE_STRUCT = "Qii"

# Size of the binary sample structure in bytes
SAMPLE_SIZE = struct.calcsize(SAMPLE_STRUCT)

# Sample flag definitions for status/flag field
# These flags indicate various conditions in temperature samples

# Bit 0: Indicates new sample data is available
SAMPLE_FLAG_NEW_DATA = 0x01

# Bit 1: Indicates a temperature threshold has been crossed
SAMPLE_FLAG_THRESHOLD = 0x02

# Bits 2-3: Mask to extract threshold type from flags
# Used to determine which type of threshold was crossed
SAMPLE_FLAG_THRESHOLD_TYPE_MASK = 0x03
