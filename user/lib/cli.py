"""
Command-line interface for NXP Simulated Temperature Sensor.

This module provides a CLI interface for interacting with the NXP Simulated Temperature
Sensor driver through both IOCTL and sysfs interfaces. It supports temperature monitoring,
trip point configuration, and real-time temperature streaming.
"""

import signal
import sys
import time
from datetime import datetime
from typing import Optional

from lib.ioctl_driver import NXPIoctlDriver
from lib.models import SimTempSample
from lib.sysfs_driver import NXPSysfsDriver


class NXPSimTempCLI:
    """
    Command-line interface for NXP Simulated Temperature Sensor.

    This class provides methods to interact with the simulated temperature sensor
    driver using both IOCTL commands and sysfs attributes. It supports temperature
    monitoring, trip point configuration, and continuous streaming of temperature data.

    Args:
        device_path: Path to the simulated temperature device node (default: /dev/simtemp)
    """

    def __init__(self, device_path: str = "/dev/simtemp") -> None:
        """
        Initialize the CLI interface with IOCTL and sysfs drivers.

        Args:
            device_path: Path to the character device for IOCTL operations
        """
        self.device_path = device_path
        self.ioctl_driver = NXPIoctlDriver(device_path)
        self.sysfs_driver = NXPSysfsDriver()

    def open_device(self) -> None:
        """Open the device for IOCTL operations."""
        self.ioctl_driver.open_device()

    def close_device(self) -> None:
        """Close the device and release resources."""
        self.ioctl_driver.close_device()

    def __enter__(self):
        """
        Context manager entry point.

        Returns:
            NXPSimTempCLI: The initialized CLI instance
        """
        self.open_device()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point - ensures device is properly closed."""
        self.close_device()

    def set_temperature(self, temperature_c: float) -> None:
        """
        Set the current temperature in Celsius via IOCTL.

        Args:
            temperature_c: Temperature value in degrees Celsius to set
        """
        self.ioctl_driver.set_temperature(temperature_c)
        print(f"Temperature set to {temperature_c:.1f}°C")

    def get_temperature(self) -> float:
        """
        Get the current temperature in Celsius via IOCTL.

        Returns:
            float: Current temperature in degrees Celsius
        """
        return self.ioctl_driver.get_temperature()

    def set_trip_point(
        self, trip_index: int, temperature_c: float, trip_type: str
    ) -> None:
        """
        Set a trip point temperature and type.

        Args:
            trip_index: Index of the trip point (0-based)
            temperature_c: Trip temperature in degrees Celsius
            trip_type: Type of trip point ('high', 'low', 'critical')
        """
        self.ioctl_driver.set_trip_point(trip_index, temperature_c, trip_type)
        print(
            f"Trip point {trip_index} set to {temperature_c:.1f}°C (type: {trip_type})"
        )

    def get_trip_point(self, trip_index: int):
        """
        Get a trip point configuration.

        Args:
            trip_index: Index of the trip point to retrieve

        Returns:
            Trip point configuration data
        """
        return self.ioctl_driver.get_trip_point(trip_index)

    def start_monitoring(self) -> None:
        """Start background temperature monitoring via IOCTL."""
        self.ioctl_driver.start_monitoring()
        print("Temperature monitoring started")

    def stop_monitoring(self) -> None:
        """Stop background temperature monitoring via IOCTL."""
        self.ioctl_driver.stop_monitoring()
        print("Temperature monitoring stopped")

    def read_temperature_sample(
        self, timeout: Optional[float] = None
    ) -> Optional[SimTempSample]:
        """
        Read binary temperature sample via blocking read operation.

        Args:
            timeout: Optional timeout in seconds for the read operation

        Returns:
            SimTempSample: Temperature sample data or None if timeout occurs
        """
        return self.ioctl_driver.read_temperature_sample(timeout)

    def read_temperature_sample_no_block(
        self, timeout: float = 0
    ) -> Optional[SimTempSample]:
        """
        Read binary temperature sample via non-blocking poll operation.

        Args:
            timeout: Poll timeout in seconds

        Returns:
            SimTempSample: Temperature sample data or None if no data available
        """
        return self.ioctl_driver.read_temperature_sample_no_block(timeout)

    def monitor_stream_continuous(
        self, duration: int = 0, poll_interval: float = 0.1
    ) -> None:
        """
        Monitor temperature continuously using stream reading with poll.

        This method uses non-blocking poll operations to read temperature samples
        from the stream interface, providing real-time temperature monitoring.

        Args:
            duration: Monitoring duration in seconds (0 = infinite)
            poll_interval: Poll interval in seconds between read attempts
        """
        print("Starting continuous stream monitoring...")
        print("Press Ctrl+C to stop")

        def signal_handler(_sig, _frame):
            """Handle SIGINT signal for graceful shutdown."""
            print("\nStream monitoring stopped")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        start_time = time.time()

        try:
            while True:
                if duration > 0 and (time.time() - start_time) >= duration:
                    print("Monitoring duration reached")
                    break

                sample = self.read_temperature_sample_no_block(poll_interval)
                if sample is not None:
                    print(sample)

        except KeyboardInterrupt:
            print("\nStream monitoring interrupted by user")

    def monitor_continuous(self, duration: int = 0) -> None:
        """
        Monitor temperature continuously using IOCTL polling.

        This method periodically reads the current temperature using IOCTL commands
        and displays it with timestamps.

        Args:
            duration: Monitoring duration in seconds (0 = infinite)
        """
        print("Starting continuous monitoring...")
        print("Press Ctrl+C to stop")

        def signal_handler(_sig, _frame):
            """Handle SIGINT signal for graceful shutdown."""
            print("\nMonitoring stopped")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        start_time = time.time()

        try:
            while True:
                if duration > 0 and (time.time() - start_time) >= duration:
                    break

                try:
                    temp = self.get_temperature()
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}] Temperature: {temp:.2f}°C")
                except RuntimeError as e:
                    print(f"Error reading temperature: {e}")

                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")

    # Sysfs interface methods

    def get_sysfs_temperature(self) -> Optional[float]:
        """
        Get current temperature via sysfs interface.

        Returns:
            float: Current temperature in Celsius, or None if unavailable
        """
        return self.sysfs_driver.get_temperature()

    def set_sysfs_temperature(self, temperature_c: float) -> bool:
        """
        Set temperature via sysfs interface.

        Args:
            temperature_c: Temperature value in Celsius to set

        Returns:
            bool: True if successful, False otherwise
        """
        return self.sysfs_driver.set_temperature(temperature_c)

    def get_sysfs_monitoring(self) -> Optional[bool]:
        """
        Get monitoring status via sysfs.

        Returns:
            bool: True if monitoring is active, False otherwise, or None if unavailable
        """
        return self.sysfs_driver.get_monitoring()

    def set_sysfs_monitoring(self, enabled: bool) -> bool:
        """
        Enable or disable monitoring via sysfs.

        Args:
            enabled: True to enable monitoring, False to disable

        Returns:
            bool: True if successful, False otherwise
        """
        return self.sysfs_driver.set_monitoring(enabled)

    def get_sysfs_sampling(self) -> Optional[int]:
        """
        Get sampling interval via sysfs.

        Returns:
            int: Sampling interval in milliseconds, or None if unavailable
        """
        return self.sysfs_driver.get_sampling()

    def set_sysfs_sampling(self, sampling_ms: int) -> bool:
        """
        Set sampling interval via sysfs.

        Args:
            sampling_ms: Sampling interval in milliseconds

        Returns:
            bool: True if successful, False otherwise
        """
        return self.sysfs_driver.set_sampling(sampling_ms)

    def get_sysfs_mode(self) -> Optional[str]:
        """
        Get operation mode via sysfs.

        Returns:
            str: Current operation mode, or None if unavailable
        """
        return self.sysfs_driver.get_mode()

    def set_sysfs_mode(self, mode: str) -> bool:
        """
        Set operation mode via sysfs.

        Args:
            mode: Operation mode to set

        Returns:
            bool: True if successful, False otherwise
        """
        return self.sysfs_driver.set_mode(mode)

    def get_sysfs_stats(self) -> Optional[dict]:
        """
        Get device statistics via sysfs.

        Returns:
            dict: Dictionary containing device statistics, or None if unavailable
        """
        return self.sysfs_driver.get_stats()

    def get_sysfs_thresholds(self) -> Optional[str]:
        """
        Get temperature thresholds via sysfs.

        Returns:
            str: Threshold configuration string, or None if unavailable
        """
        return self.sysfs_driver.get_thresholds()
