#!/usr/bin/env python3
"""
NXP Simulated Temperature Sensor CLI Tool

This module provides a command-line interface for interacting with the
NXP Simulated Temperature Sensor kernel driver.
"""

import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.cli import NXPSimTempCLI
from lib.constants import OperationMode, TripType


def main() -> int:
    """
    Main command-line interface entry point.
    """
    parser = argparse.ArgumentParser(
        description="NXP Simulated Temperature Sensor CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s get                                   # Get current temperature
  %(prog)s set 45.5                              # Set temperature to 45.5°C
  %(prog)s monitor                               # Continuous monitoring (IOCTL)
  %(prog)s stream                                # Continuous stream monitoring (read())
  %(prog)s read-stream                           # Single stream read with timeout
  %(prog)s read-stream --timeout 5.0             # Stream read with 5 second timeout
  %(prog)s mode get                              # Get current operation mode
  %(prog)s mode set noisy                        # Set operation mode to noisy
  %(prog)s sampling get                          # Get current operation sampling
  %(prog)s sampling set 1000                     # Set operation sampling to 1 sec
  %(prog)s stats                                 # Show device statistics
  %(prog)s trip set 0 80.0 THERMAL_TRIP_PASSIVE  # Set threshold trip point 0 to 80°C of type 1
                                                # trip types: THERMAL_TRIP_ACTIVE = 0
                                                #             THERMAL_TRIP_PASSIVE = 1
                                                #             THERMAL_TRIP_HOT = 2
                                                #             THERMAL_TRIP_CRITICAL = 3
  %(prog)s trip get 0                            # Get threshold trip point 0 value
  %(prog)s monitoring start                      # Start background monitoring
  %(prog)s --device /dev/custom_temp get         # Use custom device path
        """,
    )

    parser.add_argument(
        "--device",
        "-d",
        default="/dev/simtemp",
        help="Device path (default: /dev/simtemp)",
    )
    parser.add_argument(
        "--sysfs",
        "-s",
        action="store_true",
        help="Use sysfs interface instead of ioctl",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Get temperature command
    _get_parser = subparsers.add_parser("get", help="Get current temperature")

    # Set temperature command
    set_parser = subparsers.add_parser("set", help="Set temperature")
    set_parser.add_argument("temperature", type=float, help="Temperature in Celsius")

    # Monitor command (IOCTL-based)
    monitor_parser = subparsers.add_parser(
        "monitor", help="Continuous monitoring using IOCTL"
    )
    monitor_parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=0,
        help="Monitoring duration in seconds (0=infinite)",
    )

    # Stream monitoring command (read()-based)
    stream_parser = subparsers.add_parser(
        "stream", help="Continuous stream monitoring using read()"
    )
    stream_parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=0,
        help="Monitoring duration in seconds (0=infinite)",
    )
    stream_parser.add_argument(
        "--poll-interval",
        "-p",
        type=float,
        default=0.1,
        help="Poll interval in seconds (default: 0.1)",
    )

    # Single stream read command
    read_stream_parser = subparsers.add_parser(
        "read-stream", help="Single stream read operation"
    )
    read_stream_parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=None,
        help="Timeout in seconds (None=block forever)",
    )
    read_stream_parser.add_argument(
        "--non-blocking",
        "-n",
        action="store_true",
        help="Use non-blocking poll instead of blocking read",
    )

    # Trip point commands
    trip_parser = subparsers.add_parser("trip", help="Trip point operations")
    trip_subparsers = trip_parser.add_subparsers(dest="trip_command")

    trip_set_parser = trip_subparsers.add_parser("set", help="Set trip point")
    trip_set_parser.add_argument("index", type=int, help="Trip point index (0-9)")
    trip_set_parser.add_argument(
        "temperature", type=float, help="Temperature in Celsius"
    )
    trip_set_parser.add_argument("trip_type", type=str, help="Trip Type")

    trip_get_parser = trip_subparsers.add_parser("get", help="Get trip point")
    trip_get_parser.add_argument("index", type=int, help="Trip point index (0-9)")

    # Monitoring control commands
    monitoring_parser = subparsers.add_parser("monitoring", help="Monitoring control")
    monitoring_subparsers = monitoring_parser.add_subparsers(dest="monitoring_command")

    monitoring_subparsers.add_parser("start", help="Start monitoring")
    monitoring_subparsers.add_parser("stop", help="Stop monitoring")
    monitoring_subparsers.add_parser("status", help="Get monitoring status")

    # Mode control commands
    mode_parser = subparsers.add_parser("mode", help="Operation mode control")
    mode_subparsers = mode_parser.add_subparsers(dest="mode_command")

    mode_subparsers.add_parser("get", help="Get current operation mode")
    mode_set_parser = mode_subparsers.add_parser("set", help="Set operation mode")
    mode_set_parser.add_argument(
        "mode",
        choices=OperationMode.VALID_MODES,
        help="Operation mode: normal, noisy, or ramp",
    )

    # Sampling control commands
    sampling_parser = subparsers.add_parser(
        "sampling", help="Operation sampling control"
    )
    sampling_subparsers = sampling_parser.add_subparsers(dest="sampling_command")

    sampling_subparsers.add_parser("get", help="Get current operation sampling")
    sampling_set_parser = sampling_subparsers.add_parser(
        "set", help="Set operation sampling"
    )
    sampling_set_parser.add_argument(
        "sampling_ms",
        help="Operation sampling: value in miliseconds (e.g 2 secs = 2000)",
    )

    # Stats command
    _stats_parser = subparsers.add_parser("stats", help="Show device statistics")

    # Info command
    _info_parser = subparsers.add_parser("info", help="Show device information")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        cli = NXPSimTempCLI(args.device)

        with cli:
            if args.command == "get":
                if args.sysfs:
                    temp = cli.get_sysfs_temperature()
                    if temp is not None:
                        print(f"Temperature: {temp:.2f}°C (via sysfs)")
                    else:
                        print("Error: Could not read from sysfs")
                else:
                    temp = cli.get_temperature()
                    print(f"Temperature: {temp:.2f}°C")

            elif args.command == "set":
                if args.sysfs:
                    success = cli.set_sysfs_temperature(args.temperature)
                    if success:
                        print(
                            f"Temperature set to {args.temperature:.1f}°C (via sysfs)"
                        )
                    else:
                        print("Error: Could not write to sysfs")
                else:
                    cli.set_temperature(args.temperature)

            elif args.command == "monitor":
                cli.monitor_continuous(args.duration)

            elif args.command == "stream":
                cli.monitor_stream_continuous(args.duration, args.poll_interval)

            elif args.command == "read-stream":
                if args.non_blocking:
                    sample = cli.read_temperature_sample_no_block(args.timeout or 0)
                else:
                    sample = cli.read_temperature_sample(args.timeout)

                if sample is not None:
                    print(sample)
                else:
                    if args.timeout == 0:
                        print("No temperature data available (non-blocking)")
                    elif args.timeout:
                        print(
                            f"No temperature data received within {args.timeout} seconds"
                        )
                    else:
                        print("No temperature data available")

            elif args.command == "trip":
                if args.trip_command == "set":
                    cli.set_trip_point(args.index, args.temperature, args.trip_type)
                elif args.trip_command == "get":
                    temp, trip_type = cli.get_trip_point(args.index)
                    print(
                        f"Trip point {args.index}: {temp:.1f}°C - Type: {TripType.TYPE[trip_type]}"
                    )

            elif args.command == "monitoring":
                if args.monitoring_command == "start":
                    if args.sysfs:
                        success = cli.set_sysfs_monitoring(True)
                        if success:
                            print("Monitoring started (via sysfs)")
                        else:
                            print("Error: Could not write to sysfs")
                    else:
                        cli.start_monitoring()

                elif args.monitoring_command == "stop":
                    if args.sysfs:
                        success = cli.set_sysfs_monitoring(False)
                        if success:
                            print("Monitoring stopped (via sysfs)")
                        else:
                            print("Error: Could not write to sysfs")
                    else:
                        cli.stop_monitoring()

                elif args.monitoring_command == "status":
                    if args.sysfs:
                        status = cli.get_sysfs_monitoring()
                        if status is not None:
                            print(
                                f"Monitoring: {'Active' if status else 'Inactive'} (via sysfs)"
                            )
                        else:
                            print("Error: Could not read from sysfs")
                    else:
                        status = cli.get_sysfs_monitoring()
                        if status is not None:
                            print(f"Monitoring: {'Active' if status else 'Inactive'}")
                        else:
                            print("Monitoring status unavailable")

            elif args.command == "mode":
                if args.mode_command == "get":
                    mode = cli.get_sysfs_mode()
                    if mode is not None:
                        description = OperationMode.DESCRIPTION.get(
                            mode, "Unknown mode"
                        )
                        print(f"Current mode: {mode}")
                        print(f"Description: {description}")
                    else:
                        print("Error: Could not read mode from sysfs")

                elif args.mode_command == "set":
                    success = cli.set_sysfs_mode(args.mode)
                    if success:
                        description = OperationMode.DESCRIPTION.get(
                            args.mode, "Unknown mode"
                        )
                        print(f"Mode set to: {args.mode}")
                        print(f"Description: {description}")
                    else:
                        print("Error: Could not set mode via sysfs")

            elif args.command == "sampling":
                if args.sampling_command == "get":
                    sampling_ms = cli.get_sysfs_sampling()
                    if sampling_ms is not None:
                        print(f"Current sampling: {sampling_ms}")
                    else:
                        print("Error: Could not read sampling from sysfs")

                elif args.sampling_command == "set":
                    success = cli.set_sysfs_sampling(args.sampling_ms)
                    if success:
                        print(f"Sampling set to: {args.sampling_ms}")
                    else:
                        print("Error: Could not set sampling via sysfs")

            elif args.command == "stats":
                stats = cli.get_sysfs_stats()
                if stats is not None:
                    print("Device Statistics:")
                    print("=" * 30)
                    for key, value in stats.items():
                        print(f"{key:15}: {value}")
                else:
                    print("Error: Could not read statistics from sysfs")

            elif args.command == "info":
                print("NXP Simulated Temperature Sensor Information")
                print("=" * 50)
                print(f"Device path: {args.device}")

                # Try to get current temperature
                try:
                    temp = cli.get_temperature()
                    print(f"Current temperature: {temp:.2f}°C")
                except RuntimeError:
                    print("Current temperature: Unavailable")

                # Try to read from sysfs
                sysfs_temp = cli.get_sysfs_temperature()
                if sysfs_temp is not None:
                    print(f"Sysfs temperature: {sysfs_temp:.2f}°C")

                monitoring_status = cli.get_sysfs_monitoring()
                if monitoring_status is not None:
                    print(
                        f"Monitoring status: {'Active' if monitoring_status else 'Inactive'}"
                    )

                # Get current mode
                mode = cli.get_sysfs_mode()
                if mode is not None:
                    print(f"Operation mode: {mode}")

                # Get statistics
                stats = cli.get_sysfs_stats()
                if stats is not None:
                    print("\nStatistics:")
                    for key, value in stats.items():
                        print(f"  {key}: {value}")

                # Test stream reading capabilities
                print("\nStream Reading Test:")
                try:
                    sample = cli.read_temperature_sample_no_block(0.1)
                    if sample is not None:
                        print(f"  Sample: {sample}")
                    else:
                        print("  Stream read: Available (no current data)")
                except RuntimeError as e:
                    print(f"  Stream read: Unavailable ({e})")

                # Display trip points
                print("\nTrip Points:")
                for i in range(3):  # 3 trip points
                    try:
                        temp, trip_type = cli.get_trip_point(i)
                        print(
                            f"  Trip {i}: {temp:.1f}°C - Type: {TripType.TYPE[trip_type]}"
                        )
                    except (RuntimeError, ValueError) as e:
                        print(f"  Trip {i}: Unavailable ({e})")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Make sure the nxp_simtemp driver is loaded and device exists")
        return 1
    except PermissionError as e:
        print(f"Error: {e}")
        print("Try running with sudo or check device permissions")
        return 1
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
