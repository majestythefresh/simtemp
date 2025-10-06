"""
Sysfs driver interface for NXP Simulated Temperature Sensor.

This module provides access to the NXP Simulated Temperature Sensor driver
through the sysfs filesystem interface. It allows reading and writing device
attributes, configuration parameters, and statistics.
"""

from typing import Optional, Dict

from lib.constants import OperationMode


class NXPSysfsDriver:
    """
    Sysfs driver interface for NXP Simulated Temperature Sensor.

    This class provides methods to interact with the simulated temperature sensor
    driver through sysfs attributes. It supports reading temperature values,
    configuring operation modes, setting sampling intervals, and retrieving
    device statistics.
    """

    def __init__(self) -> None:
        """
        Initialize the sysfs driver with the base sysfs path.

        The sysfs base path points to the device directory containing all
        attribute files for the simulated temperature sensor.
        """
        self.sysfs_base = "/sys/class/nxp_simtemp/simtemp/device/"

    def _read_sysfs_file(self, filename: str) -> Optional[str]:
        """
        Read a sysfs file and return its content.

        Args:
            filename: Name of the sysfs attribute file to read

        Returns:
            str: Content of the sysfs file, or None if read fails
        """
        sysfs_path = f"{self.sysfs_base}{filename}"
        try:
            with open(sysfs_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            return None

    def _write_sysfs_file(self, filename: str, value: str) -> bool:
        """
        Write to a sysfs file.

        Args:
            filename: Name of the sysfs attribute file to write
            value: Value to write to the file

        Returns:
            bool: True if write successful, False otherwise
        """
        sysfs_path = f"{self.sysfs_base}{filename}"
        try:
            with open(sysfs_path, "w", encoding="utf-8") as f:
                f.write(value)
            return True
        except (FileNotFoundError, PermissionError) as e:
            print(e)
            return False

    def get_temperature(self) -> Optional[float]:
        """
        Read current temperature from sysfs interface.

        Reads the temperature value in millidegrees Celsius and converts
        it to degrees Celsius.

        Returns:
            float: Current temperature in degrees Celsius, or None if unavailable
        """
        value = self._read_sysfs_file("temperature")
        if value is not None:
            try:
                temp_mc = int(value)
                return temp_mc / 1000.0
            except ValueError:
                return None
        return None

    def set_temperature(self, temperature_c: float) -> bool:
        """
        Set temperature via sysfs interface.

        Converts the temperature from degrees Celsius to millidegrees Celsius
        and writes it to the sysfs attribute.

        Args:
            temperature_c: Temperature value in degrees Celsius to set

        Returns:
            bool: True if successful, False otherwise
        """
        temp_mc = int(temperature_c * 1000)
        return self._write_sysfs_file("temperature", str(temp_mc))

    def get_monitoring(self) -> Optional[bool]:
        """
        Get monitoring status from sysfs.

        Returns:
            bool: True if monitoring is active, False if inactive,
                  or None if status unavailable
        """
        value = self._read_sysfs_file("monitoring")
        if value is not None:
            try:
                return bool(int(value))
            except ValueError:
                return None
        return None

    def set_monitoring(self, enabled: bool) -> bool:
        """
        Set monitoring status via sysfs.

        Args:
            enabled: True to enable monitoring, False to disable

        Returns:
            bool: True if successful, False otherwise
        """
        return self._write_sysfs_file("monitoring", "1" if enabled else "0")

    def get_sampling(self) -> Optional[int]:
        """
        Get sampling interval from sysfs.

        Returns:
            int: Sampling interval in milliseconds, or None if unavailable
        """
        value = self._read_sysfs_file("sampling")
        if value is not None:
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def set_sampling(self, sampling_ms: int) -> bool:
        """
        Set sampling interval via sysfs.

        Args:
            sampling_ms: Sampling interval in milliseconds

        Returns:
            bool: True if successful, False otherwise
        """
        return self._write_sysfs_file("sampling", str(sampling_ms))

    def get_mode(self) -> Optional[str]:
        """
        Get current operation mode from sysfs.

        Returns:
            str: Current operation mode name, or None if unavailable
        """
        return self._read_sysfs_file("mode")

    def set_mode(self, mode: str) -> bool:
        """
        Set operation mode via sysfs.

        Args:
            mode: Operation mode to set (must be in OperationMode.VALID_MODES)

        Returns:
            bool: True if successful, False otherwise
        """
        if mode not in OperationMode.VALID_MODES:
            return False
        return self._write_sysfs_file("mode", mode)

    def get_stats(self) -> Optional[Dict[str, str]]:
        """
        Get device statistics from sysfs.

        Parses the statistics file which contains key-value pairs separated
        by colons and returns them as a dictionary.

        Returns:
            Dict[str, str]: Dictionary of statistic names and values,
                           or None if unavailable
        """
        value = self._read_sysfs_file("stats")
        if value is None:
            return None

        stats = {}
        for line in value.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                stats[key.strip()] = val.strip()
        return stats

    def get_thresholds(self) -> Optional[str]:
        """
        Get trip point thresholds from sysfs.

        Returns the raw threshold data from the sysfs attribute file.

        Returns:
            str: Raw threshold data string, or None if unavailable
        """
        return self._read_sysfs_file("threshold_mC")
