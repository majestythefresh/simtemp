"""
Data models for NXP Simulated Temperature Sensor.

This module defines the data structures and models used for representing
temperature samples and related data in the NXP Simulated Temperature Sensor system.
"""

import struct
import time
from datetime import datetime

from lib.constants import (
    SAMPLE_STRUCT,
    SAMPLE_SIZE,
    SAMPLE_FLAG_NEW_DATA,
    SAMPLE_FLAG_THRESHOLD,
    SAMPLE_FLAG_THRESHOLD_TYPE_MASK,
)


class SimTempSample:
    """
    Binary temperature sample structure.

    This class represents a single temperature sample read from the simulated
    temperature sensor driver. It includes timestamp, temperature data, and
    status flags in the format defined by the kernel driver.

    Args:
        timestamp_ns: Timestamp in nanoseconds (monotonic clock)
        temp_mC: Temperature in millidegrees Celsius
        flags: Status and alert flags bitfield
    """

    def __init__(self, timestamp_ns: int, temp_mC: int, flags: int):
        """
        Initialize a temperature sample.

        Args:
            timestamp_ns: Timestamp in nanoseconds from monotonic clock
            temp_mC: Temperature value in millidegrees Celsius
            flags: Bitfield containing status and alert information
        """
        self.timestamp_ns = timestamp_ns
        self.temp_mC = temp_mC
        self.flags = flags

    @property
    def temp_c(self) -> float:
        """
        Convert millicelsius to Celsius.

        Returns:
            float: Temperature in degrees Celsius
        """
        return self.temp_mC / 1000.0

    @property
    def has_new_data(self) -> bool:
        """
        Check if NEW_DATA flag is set.

        Returns:
            bool: True if sample contains new temperature data
        """
        return bool(self.flags & SAMPLE_FLAG_NEW_DATA)

    @property
    def alert(self) -> int:
        """
        Get alert status.

        Returns:
            int: 1 if temperature threshold crossed, 0 otherwise
        """
        return 1 if (self.flags & SAMPLE_FLAG_THRESHOLD) else 0

    @property
    def alert_type(self) -> int:
        """
        Extract threshold type from flags.

        Uses bits 2-3 of the flags field to determine the type of threshold
        that was crossed.

        Returns:
            int: Threshold type code
        """
        return (self.flags >> 2) & SAMPLE_FLAG_THRESHOLD_TYPE_MASK

    def get_alert_type_name(self) -> str:
        """
        Get human-readable threshold type name.

        Returns:
            str: String representation of the threshold type
        """
        return str(self.alert_type)

    def format_timestamp(self) -> str:
        """
        Format timestamp as ISO 8601 with milliseconds.

        Converts the monotonic timestamp to wall clock time by reading the
        system boot time from /proc/stat and formats it according to ISO 8601.

        Returns:
            str: ISO 8601 formatted timestamp with milliseconds
        """
        # Convert nanoseconds to seconds
        timestamp_s = self.timestamp_ns / 1_000_000_000.0

        # Get boot time to convert monotonic time to wall clock time
        try:
            # Read boot time from /proc/stat
            with open("/proc/stat", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("btime"):
                        boot_time = float(line.split()[1])
                        break
                else:
                    boot_time = time.time() - time.monotonic()
        except (IOError, OSError, ValueError):
            # Fallback: approximate boot time if /proc/stat is unavailable
            boot_time = time.time() - time.monotonic()

        # Convert monotonic time to wall clock time
        wall_time = boot_time + timestamp_s

        # Create datetime object from wall clock time
        dt = datetime.fromtimestamp(wall_time)

        # Format as ISO 8601 with milliseconds
        iso_format = dt.strftime("%Y-%m-%dT%H:%M:%S")
        milliseconds = int((wall_time % 1) * 1000)

        return f"{iso_format}.{milliseconds:03d}Z"

    def format_temperature(self) -> str:
        """
        Format temperature as X.XC.

        Returns:
            str: Formatted temperature string (e.g., "44.1C")
        """
        temp_c = self.temp_c
        temp_int = int(temp_c)
        temp_frac = int(abs(temp_c - temp_int) * 10)
        return f"{temp_int}.{temp_frac}C"

    def __str__(self) -> str:
        """
        Format sample as human-readable string.

        Format: "2025-09-22T20:15:04.123Z temp=44.1C alert=0 alert_type=THERMAL_TRIP_PASSIVE"

        Returns:
            str: Formatted string representation of the sample
        """
        timestamp = self.format_timestamp()
        temperature = self.format_temperature()
        alert_status = self.alert
        alert_type_name = self.get_alert_type_name()

        return f"{timestamp} temp={temperature} alert={alert_status} alert_type={alert_type_name}"

    @classmethod
    def from_bytes(cls, data: bytes) -> "SimTempSample":
        """
        Create SimTempSample from binary data.

        Parses the binary data according to the defined structure format
        and creates a SimTempSample instance.

        Args:
            data: Binary data containing the sample structure

        Returns:
            SimTempSample: Parsed temperature sample object

        Raises:
            ValueError: If data size doesn't match expected structure size
        """
        if len(data) != SAMPLE_SIZE:
            raise ValueError(f"Expected {SAMPLE_SIZE} bytes, got {len(data)}")

        timestamp_ns, temp_mC, flags = struct.unpack(SAMPLE_STRUCT, data)
        return cls(timestamp_ns, temp_mC, flags)
