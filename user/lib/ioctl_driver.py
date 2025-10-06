"""
IOCTL driver interface for NXP Simulated Temperature Sensor.

This module provides low-level IOCTL-based communication with the NXP Simulated
Temperature Sensor driver. It handles device operations, temperature reading/writing,
trip point configuration, and binary sample streaming.
"""

import os
import fcntl
import struct
import select
from typing import Optional, Any, Tuple

from lib.constants import NXPIoctl, TripType
from lib.models import SimTempSample, SAMPLE_SIZE


class NXPIoctlDriver:
    """
    IOCTL driver interface for NXP Simulated Temperature Sensor.

    This class provides methods to communicate with the simulated temperature
    sensor driver using IOCTL commands. It handles device file operations,
    temperature control, trip point configuration, and sample reading.

    Args:
        device_path: Path to the character device file (default: /dev/simtemp)
    """

    def __init__(self, device_path: str = "/dev/simtemp") -> None:
        """
        Initialize the IOCTL driver with device path.

        Args:
            device_path: Path to the simulated temperature device node

        Raises:
            FileNotFoundError: If the device file does not exist
            PermissionError: If read/write access to the device is not available
        """
        self.device_path = device_path
        self.fd = None
        self._check_device()

    def _check_device(self) -> None:
        """
        Verify that the device exists and is accessible.

        Raises:
            FileNotFoundError: If the device file does not exist
            PermissionError: If read/write permissions are missing
        """
        if not os.path.exists(self.device_path):
            raise FileNotFoundError(f"Device {self.device_path} not found")

        if not os.access(self.device_path, os.R_OK | os.W_OK):
            raise PermissionError(f"No read/write access to {self.device_path}")

    def open_device(self) -> None:
        """
        Open the device file for IOCTL operations.

        Raises:
            RuntimeError: If the device cannot be opened
        """
        try:
            self.fd = os.open(self.device_path, os.O_RDWR)
        except OSError as e:
            raise RuntimeError(f"Failed to open device: {e}") from e

    def close_device(self) -> None:
        """Close the device file if it's open."""
        if self.fd:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        """
        Context manager entry point.

        Returns:
            NXPIoctlDriver: The initialized driver instance
        """
        self.open_device()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point - ensures device is properly closed."""
        self.close_device()

    def _ioctl(self, cmd: int, arg: Any = None) -> int:
        """
        Perform IOCTL operation with proper argument handling.

        Args:
            cmd: IOCTL command code from NXPIoctl enum
            arg: Optional argument for the IOCTL command

        Returns:
            int: Result of the IOCTL operation

        Raises:
            RuntimeError: If device is not open or IOCTL operation fails
        """
        if self.fd is None:
            raise RuntimeError("Device not opened")

        try:
            if arg is None:
                # For _IO commands (no argument)
                return fcntl.ioctl(self.fd, cmd)
            else:
                # For commands with arguments, pack into bytes
                if isinstance(arg, int):
                    arg_buf = struct.pack("i", arg)
                elif isinstance(arg, (bytes, bytearray)):
                    arg_buf = arg
                else:
                    # Assume it's a struct that needs packing
                    arg_buf = struct.pack("i", arg)

                # For _IOR commands, we need mutable buffer
                if cmd & 0x40000000 == 0:  # _IOR commands have direction read
                    result_buf = bytearray(arg_buf)
                    fcntl.ioctl(self.fd, cmd, result_buf, True)
                    return struct.unpack("i", result_buf)[0]
                else:
                    # _IOW commands
                    return fcntl.ioctl(self.fd, cmd, arg_buf)
        except OSError as e:
            print(f"IOCTL failed (cmd: 0x{cmd:08x}): {e}")
            raise RuntimeError(f"IOCTL failed (cmd: 0x{cmd:08x}): {e}") from e

    def set_temperature(self, temperature_c: float) -> None:
        """
        Set the current temperature in Celsius.

        Args:
            temperature_c: Temperature value in degrees Celsius to set

        Raises:
            RuntimeError: If IOCTL operation fails
        """
        temp_mc = int(temperature_c * 1000)  # Convert to millicelsius
        self._ioctl(NXPIoctl.NXP_SIMTEMP_SET_TEMP, temp_mc)

    def get_temperature(self) -> float:
        """
        Get the current temperature in Celsius.

        Returns:
            float: Current temperature in degrees Celsius

        Raises:
            RuntimeError: If IOCTL operation fails or device not open
        """
        if self.fd is None:
            raise RuntimeError("Device not opened")

        temp_buf = bytearray(4)  # 4 bytes for int
        fcntl.ioctl(self.fd, NXPIoctl.NXP_SIMTEMP_GET_TEMP, temp_buf, True)
        temp_mc = struct.unpack("i", temp_buf)[0]
        return temp_mc / 1000.0

    def set_trip_point(
        self, trip_index: int, temperature_c: float, trip_type: str
    ) -> None:
        """
        Set a trip point temperature and type.

        Args:
            trip_index: Index of the trip point (0-9)
            temperature_c: Trip temperature in degrees Celsius
            trip_type: Type of trip point (must be in TripType.NAME)

        Raises:
            ValueError: If trip_index is out of range
            RuntimeError: If IOCTL operation fails
        """
        if trip_index < 0 or trip_index >= 10:
            raise ValueError("Trip index must be between 0 and 9")

        temp_mc = int(temperature_c * 1000)
        trip_data = struct.pack("iii", trip_index, temp_mc, TripType.NAME[trip_type])
        try:
            fcntl.ioctl(self.fd, NXPIoctl.NXP_SIMTEMP_SET_TRIP, trip_data)
        except OSError as e:
            raise RuntimeError(f"Failed to set trip point: {e}") from e

    def get_trip_point(self, trip_index: int) -> Tuple[float, int]:
        """
        Get a trip point configuration.

        Args:
            trip_index: Index of the trip point to retrieve (0-9)

        Returns:
            Tuple[float, int]: Temperature in Celsius and trip type code

        Raises:
            ValueError: If trip_index is out of range
            RuntimeError: If IOCTL operation fails
        """
        if trip_index < 0 or trip_index >= 10:
            raise ValueError("Trip index must be between 0 and 9")

        trip_data = struct.pack("iii", trip_index, 0, 0)
        result_buf = bytearray(trip_data)

        try:
            fcntl.ioctl(self.fd, NXPIoctl.NXP_SIMTEMP_GET_TRIP, result_buf, True)
        except OSError as e:
            raise RuntimeError(f"Failed to get trip point: {e}") from e

        _result_idx, temp_mc, trip_type = struct.unpack("iii", result_buf)
        return temp_mc / 1000.0, trip_type

    def start_monitoring(self) -> None:
        """
        Start background temperature monitoring.

        Raises:
            RuntimeError: If IOCTL operation fails
        """
        try:
            fcntl.ioctl(self.fd, NXPIoctl.NXP_SIMTEMP_START_MONITOR)
        except OSError as e:
            raise RuntimeError(f"Failed to start monitoring: {e}") from e

    def stop_monitoring(self) -> None:
        """
        Stop background temperature monitoring.

        Raises:
            RuntimeError: If IOCTL operation fails
        """
        try:
            fcntl.ioctl(self.fd, NXPIoctl.NXP_SIMTEMP_STOP_MONITOR)
        except OSError as e:
            raise RuntimeError(f"Failed to stop monitoring: {e}") from e

    def read_temperature_sample(
        self, timeout: Optional[float] = None
    ) -> Optional[SimTempSample]:
        """
        Read binary temperature sample via blocking read operation.

        Args:
            timeout: Optional timeout in seconds for the read operation

        Returns:
            SimTempSample: Temperature sample data or None if timeout occurs

        Raises:
            RuntimeError: If device not open or read operation fails
        """
        if self.fd is None:
            raise RuntimeError("Device not opened")

        # Set to blocking mode
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

        try:
            if timeout is not None:
                # Use poll with timeout
                poller = select.poll()
                poller.register(self.fd, select.POLLIN)
                events = poller.poll(int(timeout * 1000))
                if not events:
                    return None  # Timeout

            # Read binary sample data
            data = os.read(self.fd, SAMPLE_SIZE)
            if len(data) == SAMPLE_SIZE:
                return SimTempSample.from_bytes(data)
            else:
                raise RuntimeError(f"Expected {SAMPLE_SIZE} bytes, got {len(data)}")

        except OSError as e:
            if e.errno == 11:  # EAGAIN - no data available
                return None
            raise RuntimeError(f"Read failed: {e}") from e
        finally:
            # Restore original flags
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags)

    def read_temperature_sample_no_block(
        self, timeout: float = 0
    ) -> Optional[SimTempSample]:
        """
        Read binary temperature sample via non-blocking poll operation.

        Args:
            timeout: Poll timeout in seconds

        Returns:
            SimTempSample: Temperature sample data or None if no data available

        Raises:
            RuntimeError: If device not open or read operation fails
        """
        if self.fd is None:
            raise RuntimeError("Device not opened")

        # Use poll to check for data availability
        poller = select.poll()
        poller.register(self.fd, select.POLLIN)
        events = poller.poll(int(timeout * 1000))

        if events:
            # Data is available, read it
            try:
                data = os.read(self.fd, SAMPLE_SIZE)
                if len(data) == SAMPLE_SIZE:
                    return SimTempSample.from_bytes(data)
                else:
                    raise RuntimeError(f"Expected {SAMPLE_SIZE} bytes, got {len(data)}")
            except OSError as e:
                if e.errno == 11:  # EAGAIN
                    return None
                raise RuntimeError(f"Read failed: {e}") from e

        return None  # No data available
