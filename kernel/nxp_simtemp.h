/* SPDX-License-Identifier: GPL-2.0 */
/*
 * NXP Simulated Temperature Sensor Driver - Main Header
 *
 * Contains core data structures, constants, and function declarations
 * for the NXP simulated temperature sensor driver.
 */

#ifndef _NXP_SIMTEMP_H_
#define _NXP_SIMTEMP_H_

#include <linux/thermal.h>
#include <linux/types.h>
#include <linux/wait.h>

#define DRIVER_NAME "nxp_simtemp"
#define NXP_SIMTEMP_MAX_CLIENTS 10
#define DEFAULT_TEMP 25000 // 25°C in millicelsius
#define MIN_TEMP -10000    // -10°C
#define MAX_TEMP 90000     // 90°C
#define TRIP_POINTS 3
#define SAMPLING_MIN 10
#define SAMPLING_MAX 2000

/* Sample flags */
#define SAMPLE_FLAG_NEW_DATA 0x01
#define SAMPLE_FLAG_THRESHOLD 0x02
#define SAMPLE_FLAG_THRESHOLD_TYPE_MASK 0x0C

/* Operation modes */
enum nxp_simtemp_mode { MODE_NORMAL = 0, MODE_NOISY, MODE_RAMP, MODE_MAX };

static const char *const mode_names[];

/**
 * struct simtemp_sample - Binary temperature sample structure
 * @timestamp_ns: Monotonic timestamp in nanoseconds
 * @temp_mC: Temperature in milli-degree Celsius
 * @flags: Sample flags (NEW_SAMPLE, THRESHOLD_CROSSED, etc.)
 *
 * Binary record layout for temperature samples. Packed to ensure
 * consistent layout across different architectures.
 */
struct simtemp_sample {
  __u64 timestamp_ns; /* monotonic timestamp */
  __s32 temp_mC;      /* milli-degree Celsius (e.g., 44123 = 44.123 °C) */
  __u32
      flags; /* bit0=NEW_SAMPLE, bit1=THRESHOLD_CROSSED, bit2-3=THRESHOLDTYPE */
} __attribute__((packed));

/**
 * struct nxp_simtemp_client - Client structure for multiple readers
 * @node: List node for client management
 * @dev: Pointer to parent device structure
 * @data_available: Flag indicating new data is available
 * @last_temp: Last temperature value read by this client
 * @last_sample: Last temperature sample for this client
 *
 * Represents a client connection to the temperature sensor device.
 * Each open file descriptor gets its own client structure.
 */
struct nxp_simtemp_client {
  struct list_head node;
  struct nxp_simtemp_dev *dev;
  bool data_available;
  int last_temp;
  struct simtemp_sample last_sample;
};

/**
 * struct nxp_simtemp_dev - Main device structure
 * @lock: Mutex for device synchronization
 * @current_temp: Current temperature in millicelsius
 * @trip_points: Array of thermal trip point temperatures
 * @trip_types: Array of thermal trip point types
 * @num_trip_points: Number of active trip points
 * @monitoring_active: Flag indicating if monitoring is active
 * @polling_interval: Temperature polling interval in milliseconds
 * @cdev: Character device structure
 * @devno: Device number
 * @class: Device class
 * @device: Device structure
 * @read_queue: Wait queue for blocking reads
 * @client_list: List of active clients
 * @client_count: Number of active clients
 * @tzd: Thermal zone device pointer
 * @trips: Thermal trip points array
 * @monitor_thread: Temperature monitoring thread
 * @thread_running: Flag indicating if monitor thread is running
 * @mode: Current operation mode (normal, noisy, ramp)
 * @stats_updates: Counter for temperature updates
 * @stats_alerts: Counter for threshold alerts
 * @stats_last_error: Last error code encountered
 * @ramp_direction: Direction for ramp mode (1 for up, -1 for down)
 * @ramp_base_temp: Base temperature for ramp mode calculations
 *
 * Main device structure containing all device state and resources.
 */
struct nxp_simtemp_dev {
  struct mutex lock;
  int current_temp;
  int trip_points[TRIP_POINTS];
  enum thermal_trip_type trip_types[TRIP_POINTS];
  int num_trip_points;
  bool monitoring_active;
  int polling_interval; /* in milliseconds */

  struct cdev cdev;
  dev_t devno;
  struct class *class;
  struct device *device;

  wait_queue_head_t read_queue;
  struct list_head client_list;
  int client_count;

  /* Thermal zone */
  struct thermal_zone_device *tzd;
  struct thermal_trip *trips;

  /* Simulation thread */
  struct task_struct *monitor_thread;
  bool thread_running;

  /* Operation mode and statistics */
  enum nxp_simtemp_mode mode;
  unsigned long stats_updates;
  unsigned long stats_alerts;
  int stats_last_error;

  /* Ramp mode state */
  int ramp_direction;
  int ramp_base_temp;
};

#endif /* _NXP_SIMTEMP_H_ */
