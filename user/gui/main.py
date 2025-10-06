#!/usr/bin/env python3
"""
NXP Simulated Temperature Sensor GUI Monitor

A PyQt5-based GUI for monitoring temperature data from the NXP Simulated Temperature Sensor.
Displays temperature data with datetime on X-axis and colored points based on alert types.

This application provides real-time visualization of temperature data, trip point
configuration, and alert monitoring through an intuitive graphical interface.
"""

import sys
import os
import threading
import time
from datetime import datetime
from collections import deque

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QGroupBox,
    QTextEdit,
    QSpinBox,
    QSplitter,
    QFormLayout,
    QMessageBox,
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg

# Add lib directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.cli import NXPSimTempCLI
from lib.constants import TripType


class TemperatureMonitorGUI(QMainWindow):
    """
    Main GUI window for monitoring NXP temperature sensor data.

    This class provides a comprehensive GUI interface for real-time temperature
    monitoring, including data visualization, trip point configuration, and
    alert management.

    Attributes:
        device_path (str): Path to the temperature sensor device
        cli (NXPSimTempCLI): CLI interface to the temperature sensor
        is_monitoring (bool): Flag indicating if monitoring is active
        max_data_points (int): Maximum number of data points to display
        data_buffer (deque): Circular buffer for storing temperature data
        alert_colors (dict): Mapping of alert types to plot colors
        current_alert_type (str): Currently active alert type
    """

    # Signal for new data points from monitoring thread
    new_data_point = pyqtSignal(float, float, str)  # timestamp, temperature, alert_type

    def __init__(self, device_path="/dev/simtemp"):
        """
        Initialize the Temperature Monitor GUI.

        Args:
            device_path (str): Path to the temperature sensor device.
                             Defaults to "/dev/simtemp".
        """
        super().__init__()
        self.device_path = device_path
        self.cli = None
        self.is_monitoring = False
        self.max_data_points = 1000
        self.data_buffer = deque(maxlen=self.max_data_points)
        self.current_alert_type = "NORMAL/THERMAL_TRIP_ACTIVE"

        # Alert type mappings
        self.alert_types = {
            0: "NORMAL/THERMAL_TRIP_ACTIVE",
            1: "THERMAL_TRIP_PASSIVE",
            2: "THERMAL_TRIP_HOT",
            3: "THERMAL_TRIP_CRITICAL",
        }

        # Alert type colors for UI indicators
        self.alert_colors = {
            "NORMAL/THERMAL_TRIP_ACTIVE": "white",
            "THERMAL_TRIP_PASSIVE": "yellow",
            "THERMAL_TRIP_HOT": "red",
            "THERMAL_TRIP_CRITICAL": "magenta",
        }

        # Alert type display names for user interface
        self.alert_display_names = {
            "NORMAL/THERMAL_TRIP_ACTIVE": "Normal",
            "THERMAL_TRIP_PASSIVE": "Passive",
            "THERMAL_TRIP_HOT": "Hot",
            "THERMAL_TRIP_CRITICAL": "Critical",
        }

        # Alert colors for pyqtgraph plotting
        self.alert_plot_colors = {
            "NORMAL/THERMAL_TRIP_ACTIVE": "w",
            "THERMAL_TRIP_PASSIVE": "y",
            "THERMAL_TRIP_HOT": "r",
            "THERMAL_TRIP_CRITICAL": "m",
        }

        self.init_ui()
        self.init_device()

        # Connect the signal to the slot for thread-safe UI updates
        self.new_data_point.connect(self.add_data_point)

        # Timer for updating current temperature display
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_current_temperature)
        self.update_timer.start(1000)  # Update every second

    def init_ui(self):
        """Initialize the user interface components and layout."""
        self.setWindowTitle("NXP Temperature Sensor Monitor")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Controls
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Device info group
        device_group = QGroupBox("Device Information")
        device_layout = QVBoxLayout(device_group)

        self.device_status_label = QLabel("Device: Not Connected")
        device_layout.addWidget(self.device_status_label)

        # Current temperature with alert indicator
        temp_indicator_layout = QHBoxLayout()

        # Alert indicator (colored bulb)
        self.alert_indicator = QLabel()
        self.alert_indicator.setFixedSize(30, 30)
        self.alert_indicator.setStyleSheet(
            "background-color: white; border-radius: 15px; border: 2px solid gray;"
        )
        temp_indicator_layout.addWidget(self.alert_indicator)

        # Current temperature label
        self.current_temp_label = QLabel("-- °C")
        self.current_temp_label.setFont(QFont("Arial", 16, QFont.Bold))
        temp_indicator_layout.addWidget(self.current_temp_label)

        temp_indicator_layout.addStretch()
        device_layout.addLayout(temp_indicator_layout)

        # Alert status label
        self.alert_status_label = QLabel("Status: Normal")
        self.alert_status_label.setFont(QFont("Arial", 12))
        device_layout.addWidget(self.alert_status_label)

        left_layout.addWidget(device_group)

        # Monitoring control group
        monitor_group = QGroupBox("Monitoring Control")
        monitor_layout = QVBoxLayout(monitor_group)

        # Control buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Monitoring")
        self.stop_btn = QPushButton("Stop Monitoring")
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        monitor_layout.addLayout(button_layout)

        left_layout.addWidget(monitor_group)

        # Sampling control group
        sampling_group = QGroupBox("Sampling Control")
        sampling_layout = QVBoxLayout(sampling_group)

        # Sampling interval control (milliseconds)
        sampling_control_layout = QHBoxLayout()
        sampling_control_layout.addWidget(QLabel("Sampling Interval (ms):"))
        self.sampling_spin = QSpinBox()
        self.sampling_spin.setRange(50, 2000)  # 50ms to 2 seconds
        self.sampling_spin.setValue(2000)  # Default 2 seconds
        self.sampling_spin.setSingleStep(50)
        sampling_control_layout.addWidget(self.sampling_spin)

        self.set_sampling_btn = QPushButton("Set Sampling")
        sampling_control_layout.addWidget(self.set_sampling_btn)

        sampling_layout.addLayout(sampling_control_layout)

        # Current sampling display
        self.current_sampling_label = QLabel("Current: -- ms")
        sampling_layout.addWidget(self.current_sampling_label)

        left_layout.addWidget(sampling_group)

        # Trip points configuration group
        trip_config_group = QGroupBox("Trip Points Configuration")
        trip_config_layout = QFormLayout(trip_config_group)

        # Trip point 0 configuration
        self.trip0_temp = QDoubleSpinBox()
        self.trip0_temp.setRange(-10, 200)
        self.trip0_temp.setValue(80.0)
        self.trip0_temp.setSingleStep(5.0)

        self.trip0_type = QComboBox()
        self.trip0_type.addItems(
            [
                "THERMAL_TRIP_ACTIVE",
                "THERMAL_TRIP_PASSIVE",
                "THERMAL_TRIP_HOT",
                "THERMAL_TRIP_CRITICAL",
            ]
        )
        self.trip0_type.setCurrentText("THERMAL_TRIP_PASSIVE")

        self.set_trip0_btn = QPushButton("Set Trip 0")

        trip_config_layout.addRow("Trip 0 Temp (°C):", self.trip0_temp)
        trip_config_layout.addRow("Trip 0 Type:", self.trip0_type)
        trip_config_layout.addRow("", self.set_trip0_btn)

        # Trip point 1 configuration
        self.trip1_temp = QDoubleSpinBox()
        self.trip1_temp.setRange(-10, 200)
        self.trip1_temp.setValue(90.0)
        self.trip1_temp.setSingleStep(5.0)

        self.trip1_type = QComboBox()
        self.trip1_type.addItems(
            [
                "THERMAL_TRIP_ACTIVE",
                "THERMAL_TRIP_PASSIVE",
                "THERMAL_TRIP_HOT",
                "THERMAL_TRIP_CRITICAL",
            ]
        )
        self.trip1_type.setCurrentText("THERMAL_TRIP_HOT")

        self.set_trip1_btn = QPushButton("Set Trip 1")

        trip_config_layout.addRow("Trip 1 Temp (°C):", self.trip1_temp)
        trip_config_layout.addRow("Trip 1 Type:", self.trip1_type)
        trip_config_layout.addRow("", self.set_trip1_btn)

        # Trip point 2 configuration
        self.trip2_temp = QDoubleSpinBox()
        self.trip2_temp.setRange(-10, 200)
        self.trip2_temp.setValue(100.0)
        self.trip2_temp.setSingleStep(5.0)

        self.trip2_type = QComboBox()
        self.trip2_type.addItems(
            [
                "THERMAL_TRIP_ACTIVE",
                "THERMAL_TRIP_PASSIVE",
                "THERMAL_TRIP_HOT",
                "THERMAL_TRIP_CRITICAL",
            ]
        )
        self.trip2_type.setCurrentText("THERMAL_TRIP_CRITICAL")

        self.set_trip2_btn = QPushButton("Set Trip 2")

        trip_config_layout.addRow("Trip 2 Temp (°C):", self.trip2_temp)
        trip_config_layout.addRow("Trip 2 Type:", self.trip2_type)
        trip_config_layout.addRow("", self.set_trip2_btn)

        left_layout.addWidget(trip_config_group)

        # Display settings group
        display_group = QGroupBox("Display Settings")
        display_layout = QVBoxLayout(display_group)

        # Data points control
        points_layout = QHBoxLayout()
        points_layout.addWidget(QLabel("Max Data Points:"))
        self.points_spin = QSpinBox()
        self.points_spin.setRange(100, 10000)
        self.points_spin.setValue(self.max_data_points)
        self.points_spin.setSingleStep(100)
        points_layout.addWidget(self.points_spin)
        display_layout.addLayout(points_layout)

        # Auto-scroll checkbox
        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        display_layout.addWidget(self.auto_scroll_cb)

        # Clear data button
        self.clear_btn = QPushButton("Clear Data")
        display_layout.addWidget(self.clear_btn)

        left_layout.addWidget(display_group)

        # Status log
        log_group = QGroupBox("Status Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        left_layout.addWidget(log_group)

        left_layout.addStretch()

        # Right panel - Plot
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Plot widget with datetime axis
        date_axis = pg.DateAxisItem(orientation="bottom")
        self.plot_widget = pg.PlotWidget(axisItems={"bottom": date_axis})

        self.plot_widget.setLabel("left", "Temperature", "°C")
        self.plot_widget.setLabel("bottom", "Time")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend()

        # Initialize plot items
        # Main line that connects all points
        self.main_plot = self.plot_widget.plot(
            [],
            [],
            pen=pg.mkPen(color="w", width=2),
            symbol=None,  # No symbols on the main line
            name="Temperature",
        )

        # Scatter plots for different alert types
        self.scatter_plots = {}
        for alert_type in self.alert_plot_colors.keys():
            symbol = "o"
            symbol_brush = pg.mkBrush(self.alert_plot_colors[alert_type])
            self.scatter_plots[alert_type] = self.plot_widget.plot(
                [],
                [],
                pen=None,  # No lines between scatter points
                symbol=symbol,
                symbolBrush=symbol_brush,
                symbolSize=8,
                name=alert_type,
            )

        right_layout.addWidget(self.plot_widget)

        # Add widgets to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 1000])

        main_layout.addWidget(splitter)

        # Connect signals
        self.start_btn.clicked.connect(self.start_monitoring)
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.clear_btn.clicked.connect(self.clear_data)
        self.points_spin.valueChanged.connect(self.update_buffer_size)
        self.set_sampling_btn.clicked.connect(self.set_sampling_interval)
        self.set_trip0_btn.clicked.connect(lambda: self.set_trip_point(0))
        self.set_trip1_btn.clicked.connect(lambda: self.set_trip_point(1))
        self.set_trip2_btn.clicked.connect(lambda: self.set_trip_point(2))

        self.log_message("GUI initialized successfully")

    def update_current_temperature(self):
        """Update the current temperature display and alert indicator."""
        if not self.cli:
            return

        try:
            # Get current temperature
            current_temp = self.cli.get_temperature()

            # Update temperature label
            self.current_temp_label.setText(f"{current_temp:.2f} °C")

            # Update alert status based on current temperature and trip points
            self.update_alert_status(current_temp)

        except Exception:
            self.current_temp_label.setText("-- °C")
            self.alert_status_label.setText("Status: Error")
            self.alert_indicator.setStyleSheet(
                "background-color: gray; border-radius: 15px; border: 2px solid darkgray;"
            )

    def update_alert_status(self, temperature):
        """
        Update the alert status based on current temperature.

        Args:
            temperature (float): Current temperature in Celsius
        """
        try:
            # Determine alert type based on temperature and trip points
            alert_type = "NORMAL/THERMAL_TRIP_ACTIVE"

            # Get trip point configurations
            trip = []
            for i in range(3):
                trip_temp, trip_type = self.cli.get_trip_point(i)
                trip.append((trip_temp, trip_type))

            # Determine highest priority alert based on trip points
            alert_type = 0
            for trip_temp, trip_type in trip:
                if temperature > trip_temp and trip_type != 0:
                    alert_type = trip_type
            alert_type = self.alert_types.get(alert_type, 0)

            # Update current alert type
            self.current_alert_type = alert_type

            # Update alert indicator color
            color = self.alert_colors.get(alert_type, "white")
            self.alert_indicator.setStyleSheet(
                f"background-color: {color}; border-radius: 15px; border: 2px solid darkgray;"
            )

            # Update alert status text
            display_name = self.alert_display_names.get(alert_type, "Unknown")
            self.alert_status_label.setText(f"Status: {display_name}")

        except Exception:
            self.alert_status_label.setText("Status: Error")
            self.alert_indicator.setStyleSheet(
                "background-color: gray; border-radius: 15px; border: 2px solid darkgray;"
            )

    def init_device(self):
        """Initialize the temperature sensor device connection."""
        try:
            self.cli = NXPSimTempCLI(self.device_path)
            self.cli.__enter__()

            # Test device connection
            temp = self.cli.get_temperature()
            self.device_status_label.setText(f"Device: Connected ({self.device_path})")
            self.current_temp_label.setText(f"{temp:.2f} °C")
            self.update_alert_status(temp)

            # Load current sampling interval
            self.load_sampling_interval()

            # Load trip points configuration into widgets
            self.load_trip_points_config()

            self.log_message(
                f"Device initialized successfully. Current temperature: {temp:.2f}°C"
            )

        except Exception as e:
            self.device_status_label.setText(f"Device: Error - {str(e)}")
            self.log_message(f"Error initializing device: {str(e)}")

    def load_sampling_interval(self):
        """Load and display current sampling interval from device."""
        try:
            sampling_ms = self.cli.get_sysfs_sampling()
            if sampling_ms is not None:
                self.current_sampling_label.setText(f"Current: {sampling_ms} ms")
                self.sampling_spin.setValue(sampling_ms)
                self.log_message(f"Current sampling interval: {sampling_ms} ms")
            else:
                self.current_sampling_label.setText("Current: Unknown")
                self.log_message("Could not read sampling interval from device")
        except Exception as e:
            self.current_sampling_label.setText("Current: Error")
            self.log_message(f"Error reading sampling interval: {str(e)}")

    def load_trip_points_config(self):
        """Load current trip point values into configuration widgets."""
        try:
            # Load trip point 0
            try:
                temp0, trip_type0 = self.cli.get_trip_point(0)
                self.trip0_temp.setValue(temp0)
                # Convert trip type number to string name
                trip_type_name0 = TripType.TYPE.get(trip_type0, "THERMAL_TRIP_PASSIVE")
                index0 = self.trip0_type.findText(trip_type_name0)
                if index0 >= 0:
                    self.trip0_type.setCurrentIndex(index0)
                self.log_message(f"Loaded Trip 0: {temp0}°C, {trip_type_name0}")
            except (RuntimeError, ValueError) as e:
                self.log_message(f"Could not load Trip 0: {str(e)}")

            # Load trip point 1
            try:
                temp1, trip_type1 = self.cli.get_trip_point(1)
                self.trip1_temp.setValue(temp1)
                trip_type_name1 = TripType.TYPE.get(trip_type1, "THERMAL_TRIP_HOT")
                index1 = self.trip1_type.findText(trip_type_name1)
                if index1 >= 0:
                    self.trip1_type.setCurrentIndex(index1)
                self.log_message(f"Loaded Trip 1: {temp1}°C, {trip_type_name1}")
            except (RuntimeError, ValueError) as e:
                self.log_message(f"Could not load Trip 1: {str(e)}")

            # Load trip point 2
            try:
                temp2, trip_type2 = self.cli.get_trip_point(2)
                self.trip2_temp.setValue(temp2)
                trip_type_name2 = TripType.TYPE.get(trip_type2, "THERMAL_TRIP_CRITICAL")
                index2 = self.trip2_type.findText(trip_type_name2)
                if index2 >= 0:
                    self.trip2_type.setCurrentIndex(index2)
                self.log_message(f"Loaded Trip 2: {temp2}°C, {trip_type_name2}")
            except (RuntimeError, ValueError) as e:
                self.log_message(f"Could not load Trip 2: {str(e)}")

        except Exception as e:
            self.log_message(f"Error loading trip points configuration: {str(e)}")

    def set_sampling_interval(self):
        """Set the sampling interval on the device."""
        if not self.cli:
            self.log_message("Error: Device not initialized")
            return

        try:
            sampling_ms = self.sampling_spin.value()
            success = self.cli.set_sysfs_sampling(sampling_ms)

            if success:
                self.current_sampling_label.setText(f"Current: {sampling_ms} ms")
                self.sampling_spin.setValue(sampling_ms)
                self.log_message(f"Sampling interval set to {sampling_ms} ms")
            else:
                self.log_message("Error: Failed to set sampling interval")

        except Exception as e:
            self.log_message(f"Error setting sampling interval: {str(e)}")

    def set_trip_point(self, index):
        """
        Set a trip point on the device.

        Args:
            index (int): Trip point index (0, 1, or 2)
        """
        if not self.cli:
            self.log_message("Error: Device not initialized")
            return

        try:
            # Get the temperature and type based on index
            if index == 0:
                temperature = self.trip0_temp.value()
                trip_type = self.trip0_type.currentText()
            elif index == 1:
                temperature = self.trip1_temp.value()
                trip_type = self.trip1_type.currentText()
            elif index == 2:
                temperature = self.trip2_temp.value()
                trip_type = self.trip2_type.currentText()
            else:
                self.log_message(f"Error: Invalid trip point index {index}")
                return

            # Set the trip point
            self.cli.set_trip_point(index, temperature, trip_type)
            self.log_message(f"Trip point {index} set to {temperature}°C ({trip_type})")

        except Exception as e:
            self.log_message(f"Error setting trip point {index}: {str(e)}")

    def start_monitoring(self):
        """Start temperature monitoring and data streaming."""
        if not self.cli:
            self.log_message("Error: Device not initialized")
            return

        try:
            self.is_monitoring = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)

            # Start stream monitoring in separate thread
            self.stream_thread = threading.Thread(
                target=self.stream_monitoring_worker, daemon=True
            )
            self.stream_thread.start()
            self.log_message("Started Chart stream monitoring")

            # Enable monitoring via sysfs
            success = self.cli.set_sysfs_monitoring(True)
            if success:
                self.log_message("Monitoring started (via sysfs)")
            else:
                self.log_message("Error: Could not write to sysfs")

        except Exception as e:
            self.log_message(f"Error starting monitoring: {str(e)}")
            self.stop_monitoring()

    def stop_monitoring(self):
        """Stop temperature monitoring and data streaming."""
        self.is_monitoring = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log_message("Chart Monitoring stopped")

        # Disable monitoring via sysfs
        success = self.cli.set_sysfs_monitoring(False)
        if success:
            self.log_message("Monitoring stopped (via sysfs)")
        else:
            self.log_message("Error: Could not write to sysfs")

    def stream_monitoring_worker(self):
        """Worker function for stream monitoring in separate thread."""
        try:
            while self.is_monitoring:
                sample = self.cli.read_temperature_sample_no_block(0.1)
                if sample is not None:
                    sample_str = str(sample).strip()

                    try:
                        parts = sample_str.split()
                        if len(parts) >= 4:
                            timestamp_str = parts[0]
                            temp_part = parts[1]
                            alert_type_part = parts[3]

                            temperature = float(
                                temp_part.split("=")[1].replace("C", "")
                            )
                            alert_type_num = int(alert_type_part.split("=")[1])

                            alert_type_map = {
                                0: "NORMAL/THERMAL_TRIP_ACTIVE",
                                1: "THERMAL_TRIP_PASSIVE",
                                2: "THERMAL_TRIP_HOT",
                                3: "THERMAL_TRIP_CRITICAL",
                            }
                            alert_type = alert_type_map.get(alert_type_num, "UNKNOWN")

                            if timestamp_str.endswith("Z"):
                                timestamp_str = timestamp_str[:-1] + "+00:00"
                            dt = datetime.fromisoformat(timestamp_str)
                            timestamp = dt.timestamp()

                            self.new_data_point.emit(timestamp, temperature, alert_type)

                    except Exception as e:
                        print(f"Error parsing sample: {sample_str} - {e}")

                time.sleep(0.01)

        except Exception as e:
            self.new_data_point.emit(
                0, 0, f"ERROR:{str(e)}"
            )  # Emit error as data point

    def add_data_point(self, timestamp, temperature, alert_type):
        """
        Add a data point to the buffer and update plot.

        Args:
            timestamp (float): Unix timestamp of the data point
            temperature (float): Temperature value in Celsius
            alert_type (str): Type of alert for this data point
        """
        # Convert timestamp to datetime for display with timezone offset
        CENTRAL_TIME_OFFSET_HOURS = +6  # UTC to CT conversion

        # Apply offset to get CT timestamp for plotting
        ct_timestamp = timestamp + (CENTRAL_TIME_OFFSET_HOURS * 3600)
        dt = datetime.fromtimestamp(ct_timestamp)

        # Add to buffer - store the CT-adjusted timestamp for plotting
        self.data_buffer.append(
            {
                "timestamp": ct_timestamp,  # Store CT timestamp instead of UTC
                "datetime": dt,
                "temperature": temperature,
                "alert_type": alert_type,
            }
        )

        # Update plot
        self.update_plot()

        # Log significant events
        if alert_type != "NORMAL/THERMAL_TRIP_ACTIVE":
            self.log_message(
                f"Alert: {alert_type} at {dt.strftime('%H:%M:%S')}, Temp: {temperature:.2f}°C"
            )

    def update_plot(self):
        """Update the plot with current data using datetime on X-axis."""
        if not self.data_buffer:
            return

        # Sort data by timestamp to ensure proper connection
        sorted_data = sorted(self.data_buffer, key=lambda x: x["timestamp"])

        # Extract all timestamps and temperatures for the main line
        all_timestamps = [point["timestamp"] for point in sorted_data]
        all_temperatures = [point["temperature"] for point in sorted_data]

        # Update the main continuous line
        self.main_plot.setData(all_timestamps, all_temperatures)

        # Update scatter plots for each alert type
        for alert_type in self.alert_plot_colors.keys():
            # Filter data for this alert type
            alert_data = [
                point for point in sorted_data if point["alert_type"] == alert_type
            ]

            if alert_data:
                alert_timestamps = [point["timestamp"] for point in alert_data]
                alert_temperatures = [point["temperature"] for point in alert_data]
                self.scatter_plots[alert_type].setData(
                    alert_timestamps, alert_temperatures
                )
            else:
                self.scatter_plots[alert_type].setData([], [])

        # Auto-scroll if enabled
        if self.auto_scroll_cb.isChecked() and self.data_buffer:
            latest_time = max(point["timestamp"] for point in self.data_buffer)
            # Show last 5 minutes
            self.plot_widget.setXRange(latest_time - 300, latest_time + 30)

    def clear_data(self):
        """Clear all data from the buffer and plot."""
        self.data_buffer.clear()
        self.main_plot.setData([], [])
        for scatter_plot in self.scatter_plots.values():
            scatter_plot.setData([], [])
        self.log_message("Data cleared")

    def update_buffer_size(self, new_size):
        """
        Update the data buffer size.

        Args:
            new_size (int): New maximum number of data points to store
        """
        self.max_data_points = new_size
        new_buffer = deque(self.data_buffer, maxlen=new_size)
        self.data_buffer = new_buffer
        self.update_plot()
        self.log_message(f"Buffer size updated to {new_size} points")

    def log_message(self, message):
        """
        Add a message to the log.

        Args:
            message (str): Message to add to the log
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """
        Handle application closure.

        Args:
            event: Close event
        """
        self.stop_monitoring()
        if self.update_timer.isActive():
            self.update_timer.stop()
        if self.cli:
            try:
                self.cli.__exit__(None, None, None)
            except:
                pass
        event.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Parse command line arguments for device path
    device_path = "/dev/simtemp"
    if len(sys.argv) > 1:
        device_path = sys.argv[1]

    # Create and show main window
    window = TemperatureMonitorGUI(device_path)
    window.show()

    # Start the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
