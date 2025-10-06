// SPDX-License-Identifier: GPL-2.0
/*
 * NXP Simulated Temperature Sensor Driver
 *
 * Simulates a temperature sensor with configurable temperature values,
 * trip points, and thermal zone integration. Provides binary temperature
 * samples via read() and poll() interfaces.
 */

#include <linux/cdev.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/kthread.h>
#include <linux/ktime.h>
#include <linux/list.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/poll.h>
#include <linux/random.h>
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/thermal.h>
#include <linux/time64.h>
#include <linux/timer.h>
#include <linux/types.h>
#include <linux/uaccess.h>
#include <linux/wait.h>

#include "nxp_simtemp.h"
#include "nxp_simtemp_ioctl.h"

static const char *const mode_names[] = {
    [MODE_NORMAL] = "normal",
    [MODE_NOISY] = "noisy",
    [MODE_RAMP] = "ramp",
};

/**
 * nxp_simtemp_generate_sample - Generate binary temperature sample
 * @dev: Pointer to device structure
 * @client: Pointer to client structure
 *
 * Generates a binary temperature sample with timestamp, temperature,
 * and alert flags. Uses monotonic time for consistent timing.
 *
 * Context: Any context with device lock held
 */
static void nxp_simtemp_generate_sample(struct nxp_simtemp_dev *dev,
                                        struct nxp_simtemp_client *client) {
  struct simtemp_sample *sample = &client->last_sample;
  int i;
  bool alert_triggered = false;

  /* Get monotonic timestamp */
  sample->timestamp_ns = ktime_get_ns();

  /* Set temperature */
  sample->temp_mC = dev->current_temp;

  /* Determine flags */
  sample->flags = SAMPLE_FLAG_NEW_DATA;

  /* Check if any trip point threshold has been crossed */
  for (i = 0; i < TRIP_POINTS; i++) {
    if (dev->current_temp > dev->trip_points[i] &&
        dev->trip_types[i] != THERMAL_TRIP_ACTIVE) {
      sample->flags |= SAMPLE_FLAG_THRESHOLD; /* Alert flag */
      /* Clear bits 2-3 and set threshold type */
      sample->flags = (sample->flags & ~SAMPLE_FLAG_THRESHOLD_TYPE_MASK) |
                      (dev->trip_types[i] << 2);
      alert_triggered = true;
    }
  }
}

/**
 * nxp_simtemp_simulate_temperature_change - Simulate temperature change based
 * on mode
 * @dev: Pointer to device structure
 *
 * Simulates temperature changes according to the current operation mode:
 * - NORMAL: Small variations around current temperature
 * - NOISY: Random noise added to temperature
 * - RAMP: Continuous ramp up and down between limits
 *
 * Context: Must be called with device lock held
 */
static void
nxp_simtemp_simulate_temperature_change(struct nxp_simtemp_dev *dev) {
  int new_temp = dev->current_temp;

  switch (dev->mode) {
  case MODE_NORMAL:
    /* Normal mode: small random variations */
    if (new_temp <= 80000) {
      new_temp += 500; /* 0.5°C increase */
    } else {
      new_temp -= 35000; /* 35.00°C decrease */
    }
    break;

  case MODE_NOISY:
    /* Noisy mode: add random noise */
    {
      int base_temp, noise;

      /* Generate random base temperature between MIN_TEMP and MAX_TEMP */
      get_random_bytes(&base_temp, sizeof(base_temp));
      base_temp = MIN_TEMP + (abs(base_temp) % (MAX_TEMP - MIN_TEMP + 1));

      /* Generate noise ±1°C */
      get_random_bytes(&noise, sizeof(noise));
      noise = (noise % 2001) - 1000; /* ±1°C noise */

      new_temp = base_temp + noise;
    }
    break;

  case MODE_RAMP:

    /* Reverse direction at limits */
    if (new_temp <= MAX_TEMP) {
      new_temp += 5000;
    }
    if (new_temp > MAX_TEMP) {
      new_temp = MIN_TEMP;
    }
    break;

  default:
    /* Default to normal mode */
    if (new_temp <= 80000) {
      new_temp += 500;
    } else {
      new_temp -= 35000;
    }
    break;
  }

  /* Clamp temperature to valid range */
  if (new_temp < MIN_TEMP)
    new_temp = MIN_TEMP;
  if (new_temp > MAX_TEMP)
    new_temp = MAX_TEMP;

  dev->current_temp = new_temp;
  dev->stats_updates++;
}

/**
 * nxp_simtemp_open - Open device function
 * @inode: Pointer to inode structure
 * @file: Pointer to file structure
 *
 * Allocates and initializes a new client structure for the opening process.
 * Adds client to device's client list and generates initial sample data.
 *
 * Return: 0 on success, negative error code on failure
 */
static int nxp_simtemp_open(struct inode *inode, struct file *file) {
  struct nxp_simtemp_dev *dev =
      container_of(inode->i_cdev, struct nxp_simtemp_dev, cdev);
  struct nxp_simtemp_client *client;

  client = kzalloc(sizeof(*client), GFP_KERNEL);
  if (!client)
    return -ENOMEM;

  mutex_lock(&dev->lock);

  if (dev->client_count >= NXP_SIMTEMP_MAX_CLIENTS) {
    mutex_unlock(&dev->lock);
    kfree(client);
    return -EBUSY;
  }

  client->dev = dev;
  client->data_available = false;
  client->last_temp = dev->current_temp;

  /* Generate initial sample */
  nxp_simtemp_generate_sample(dev, client);

  list_add(&client->node, &dev->client_list);
  dev->client_count++;

  file->private_data = client;

  mutex_unlock(&dev->lock);

  dev_dbg(dev->device, "Device opened by client %p\n", client);
  return 0;
}

/**
 * nxp_simtemp_release - Release device function
 * @inode: Pointer to inode structure
 * @file: Pointer to file structure
 *
 * Cleans up client resources, removes client from device's client list,
 * and frees client structure.
 *
 * Return: 0 on success
 */
static int nxp_simtemp_release(struct inode *inode, struct file *file) {
  struct nxp_simtemp_client *client = file->private_data;
  struct nxp_simtemp_dev *dev = client->dev;

  mutex_lock(&dev->lock);
  list_del(&client->node);
  dev->client_count--;
  mutex_unlock(&dev->lock);

  kfree(client);
  dev_dbg(dev->device, "Device closed\n");
  return 0;
}

/**
 * nxp_simtemp_read - Read device function
 * @file: Pointer to file structure
 * @buf: Userspace buffer to read into
 * @count: Size of userspace buffer
 * @ppos: File position pointer (unused)
 *
 * Reads binary temperature sample to userspace. Supports both blocking
 * and non-blocking I/O. For blocking reads, waits until new data is available.
 *
 * Return: Number of bytes read on success, negative error code on failure
 */
static ssize_t nxp_simtemp_read(struct file *file, char __user *buf,
                                size_t count, loff_t *ppos) {
  struct nxp_simtemp_client *client = file->private_data;
  struct nxp_simtemp_dev *dev = client->dev;
  ssize_t ret;

  /* For non-blocking reads, return current data immediately */
  if (file->f_flags & O_NONBLOCK) {
    mutex_lock(&dev->lock);
    if (!client->data_available) {
      mutex_unlock(&dev->lock);
      dev->stats_last_error = -EAGAIN;
      return -EAGAIN;
    }
  } else {
    /* For blocking reads, wait for new data */
    if (wait_event_interruptible(dev->read_queue, client->data_available)) {
      dev->stats_last_error = -ERESTARTSYS;
      return -ERESTARTSYS;
    }
    mutex_lock(&dev->lock);
  }

  /* Check if buffer is large enough for one sample */
  if (count < sizeof(struct simtemp_sample)) {
    mutex_unlock(&dev->lock);
    dev->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  /* Copy binary sample to userspace */
  ret = copy_to_user(buf, &client->last_sample, sizeof(struct simtemp_sample));
  if (ret) {
    mutex_unlock(&dev->lock);
    dev->stats_last_error = -EFAULT;
    return -EFAULT;
  }

  client->data_available = false;
  mutex_unlock(&dev->lock);

  return sizeof(struct simtemp_sample);
}

/**
 * nxp_simtemp_poll - Poll device function
 * @file: Pointer to file structure
 * @wait: Poll table structure
 *
 * Checks if device is ready for reading. Returns mask indicating
 * read availability when new temperature data is available.
 *
 * Return: Poll mask indicating read readiness
 */
static __poll_t nxp_simtemp_poll(struct file *file, poll_table *wait) {
  struct nxp_simtemp_client *client = file->private_data;
  struct nxp_simtemp_dev *dev = client->dev;
  __poll_t mask = 0;

  poll_wait(file, &dev->read_queue, wait);

  mutex_lock(&dev->lock);
  if (client->data_available || client->last_temp != dev->current_temp) {
    mask |= EPOLLIN | EPOLLRDNORM;
  }
  mutex_unlock(&dev->lock);

  return mask;
}

/**
 * nxp_simtemp_validate_user_input - Validate user input parameters
 * @ptr: User space pointer to validate
 * @size: Size of the data to validate
 * @write: True if validating for write access, false for read
 *
 * Performs comprehensive validation of user space pointers including
 * access_ok() checks and pointer alignment/sanity validation.
 *
 * Return: 0 if valid, negative error code otherwise
 */
static int nxp_simtemp_validate_user_input(const void __user *ptr, size_t size,
                                           bool write) {
  if (!ptr)
    return -EFAULT;

  /* Check if user space pointer is accessible */
  if (!access_ok(ptr, size))
    return -EFAULT;

  /* Additional sanity checks for larger buffers */
  if (size > PAGE_SIZE)
    return -EINVAL;

  return 0;
}

/**
 * nxp_simtemp_ioctl - IOCTL device function
 * @file: Pointer to file structure
 * @cmd: IOCTL command
 * @arg: IOCTL argument
 *
 * Handles device control operations:
 * - Set/get current temperature
 * - Set/get trip points
 * - Start/stop temperature monitoring
 *
 * Return: 0 on success, negative error code on failure
 */
static long nxp_simtemp_ioctl(struct file *file, unsigned int cmd,
                              unsigned long arg) {
  struct nxp_simtemp_client *client = file->private_data;
  struct nxp_simtemp_dev *dev = client->dev;
  int temp;
  int trip_data[3];
  int ret = 0;

  switch (cmd) {
  case NXP_SIMTEMP_SET_TEMP:
    /* Validate user input for write operation */
    ret = nxp_simtemp_validate_user_input((const void __user *)arg,
                                          sizeof(temp), true);
    if (ret) {
      dev->stats_last_error = ret;
      return ret;
    }

    if (copy_from_user(&temp, (int __user *)arg, sizeof(temp))) {
      dev->stats_last_error = -EFAULT;
      return -EFAULT;
    }

    if (temp < MIN_TEMP || temp > MAX_TEMP) {
      dev->stats_last_error = -EINVAL;
      return -EINVAL;
    }

    mutex_lock(&dev->lock);
    dev->current_temp = temp;
    dev->stats_updates++;

    /* Reset ramp base when temperature is manually set */
    if (dev->mode == MODE_RAMP) {
      dev->ramp_base_temp = temp;
    }

    /* Notify all clients of temperature change */
    struct nxp_simtemp_client *c;
    list_for_each_entry(c, &dev->client_list, node) {
      nxp_simtemp_generate_sample(dev, c);
      c->data_available = true;
      c->last_temp = temp;
    }
    wake_up_interruptible(&dev->read_queue);

    /* Update thermal zone */
    if (dev->tzd)
      thermal_zone_device_update(dev->tzd, THERMAL_EVENT_UNSPECIFIED);

    mutex_unlock(&dev->lock);
    dev_info(dev->device, "Temperature set to %d°C\n", temp / 1000);
    break;

  case NXP_SIMTEMP_GET_TEMP:
    mutex_lock(&dev->lock);
    temp = dev->current_temp;
    mutex_unlock(&dev->lock);

    /* Validate user input for read operation */
    ret = nxp_simtemp_validate_user_input((const void __user *)arg,
                                          sizeof(temp), false);
    if (ret) {
      dev->stats_last_error = ret;
      return ret;
    }

    if (copy_to_user((int __user *)arg, &temp, sizeof(temp))) {
      dev->stats_last_error = -EFAULT;
      return -EFAULT;
    }
    break;

  case NXP_SIMTEMP_SET_TRIP:
    /* Validate user input for write operation */
    ret = nxp_simtemp_validate_user_input((const void __user *)arg,
                                          sizeof(trip_data), true);
    if (ret) {
      dev->stats_last_error = ret;
      return ret;
    }

    if (copy_from_user(trip_data, (int __user *)arg, sizeof(trip_data))) {
      dev->stats_last_error = -EFAULT;
      return -EFAULT;
    }

    if (trip_data[0] < 0 || trip_data[0] >= TRIP_POINTS) {
      dev->stats_last_error = -EINVAL;
      return -EINVAL;
    }

    mutex_lock(&dev->lock);
    dev->trip_points[trip_data[0]] = trip_data[1];
    dev->trip_types[trip_data[0]] = trip_data[2];

    /* Update thermal trip if it exists */
    if (dev->trips && trip_data[0] < dev->num_trip_points) {
      dev->trips[trip_data[0]].temperature = trip_data[1];
      dev->trips[trip_data[0]].type = trip_data[2];
    }
    mutex_unlock(&dev->lock);
    break;

  case NXP_SIMTEMP_GET_TRIP:
    /* Validate user input for read operation */
    ret = nxp_simtemp_validate_user_input((const void __user *)arg,
                                          sizeof(trip_data), false);
    if (ret) {
      dev->stats_last_error = ret;
      return ret;
    }

    if (copy_from_user(trip_data, (int __user *)arg, sizeof(trip_data))) {
      dev->stats_last_error = -EFAULT;
      return -EFAULT;
    }

    if (trip_data[0] < 0 || trip_data[0] >= TRIP_POINTS) {
      dev->stats_last_error = -EINVAL;
      return -EINVAL;
    }

    mutex_lock(&dev->lock);
    trip_data[1] = dev->trip_points[trip_data[0]];
    trip_data[2] = dev->trip_types[trip_data[0]];
    mutex_unlock(&dev->lock);

    if (copy_to_user((int __user *)arg, trip_data, sizeof(trip_data))) {
      dev->stats_last_error = -EFAULT;
      return -EFAULT;
    }
    break;

  case NXP_SIMTEMP_START_MONITOR:
    mutex_lock(&dev->lock);
    dev->monitoring_active = true;
    mutex_unlock(&dev->lock);
    dev_info(dev->device, "Temperature monitoring started\n");
    break;

  case NXP_SIMTEMP_STOP_MONITOR:
    mutex_lock(&dev->lock);
    dev->monitoring_active = false;
    mutex_unlock(&dev->lock);
    dev_info(dev->device, "Temperature monitoring stopped\n");
    break;

  default:
    ret = -ENOTTY;
    break;
  }

  return ret;
}

/**
 * nxp_simtemp_fops - File operations structure for character device
 *
 * Defines the file operations supported by the temperature sensor device.
 */
static const struct file_operations nxp_simtemp_fops = {
    .owner = THIS_MODULE,
    .open = nxp_simtemp_open,
    .release = nxp_simtemp_release,
    .read = nxp_simtemp_read,
    .poll = nxp_simtemp_poll,
    .unlocked_ioctl = nxp_simtemp_ioctl,
    .compat_ioctl = nxp_simtemp_ioctl,
};

/**
 * nxp_simtemp_get_temp - Get temperature for thermal zone
 * @tzd: Thermal zone device pointer
 * @temp: Pointer to store temperature value
 *
 * Retrieves current temperature from device for thermal subsystem.
 *
 * Return: 0 on success
 */
static int nxp_simtemp_get_temp(struct thermal_zone_device *tzd, int *temp) {
  struct nxp_simtemp_dev *dev = thermal_zone_device_priv(tzd);

  mutex_lock(&dev->lock);
  *temp = dev->current_temp;
  mutex_unlock(&dev->lock);

  return 0;
}

/**
 * nxp_simtemp_set_trip_temp - Set trip point temperature
 * @tzd: Thermal zone device pointer
 * @trip: Trip point index
 * @temp: Temperature value to set
 *
 * Sets thermal trip point temperature for specified trip point.
 *
 * Return: 0 on success, negative error code on failure
 */
static int nxp_simtemp_set_trip_temp(struct thermal_zone_device *tzd, int trip,
                                     int temp) {
  struct nxp_simtemp_dev *dev = thermal_zone_device_priv(tzd);

  if (trip < 0 || trip >= dev->num_trip_points) {
    dev->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  mutex_lock(&dev->lock);
  dev->trip_points[trip] = temp;
  if (dev->trips) {
    dev->trips[trip].temperature = temp;
  }
  mutex_unlock(&dev->lock);

  return 0;
}

/**
 * nxp_simtemp_thermal_ops - Thermal zone device operations
 *
 * Defines the thermal zone operations for the temperature sensor.
 */
static struct thermal_zone_device_ops nxp_simtemp_thermal_ops = {
    .get_temp = nxp_simtemp_get_temp,
    .set_trip_temp = nxp_simtemp_set_trip_temp,
};

/**
 * nxp_simtemp_monitor_thread - Temperature monitoring thread function
 * @data: Pointer to device structure
 *
 * Background thread that simulates temperature variations and
 * notifies clients of changes. Runs periodically based on polling interval.
 *
 * Return: 0 on thread exit
 */
static int nxp_simtemp_monitor_thread(void *data) {
  struct nxp_simtemp_dev *dev = data;
  bool alert_triggered = false;
  int i;

  while (!kthread_should_stop()) {
    msleep_interruptible(dev->polling_interval);

    if (!dev->monitoring_active)
      continue;

    mutex_lock(&dev->lock);

    /* Simulate temperature change based on current mode */
    nxp_simtemp_simulate_temperature_change(dev);

    /* Notify clients */
    struct nxp_simtemp_client *client;
    list_for_each_entry(client, &dev->client_list, node) {
      if (client->last_temp != dev->current_temp) {
        nxp_simtemp_generate_sample(dev, client);
        client->data_available = true;
        client->last_temp = dev->current_temp;
      }
    }

    /* Check if any trip point threshold has been crossed to
    raise alert counter*/
    alert_triggered = false;
    for (i = 0; i < TRIP_POINTS; i++) {
      if (dev->current_temp > dev->trip_points[i] &&
          dev->trip_types[i] != THERMAL_TRIP_ACTIVE) {
        alert_triggered = true;
        break;
      }
    }
    /* Update statistics */
    if (alert_triggered) {
      dev->stats_alerts++;
    }
    wake_up_interruptible(&dev->read_queue);

    /* Update thermal zone */
    if (dev->tzd)
      thermal_zone_device_update(dev->tzd, THERMAL_EVENT_UNSPECIFIED);

    mutex_unlock(&dev->lock);
  }

  return 0;
}

/* Sysfs attributes */

/**
 * temperature_show - Show current temperature
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer to store temperature string
 *
 * Return: Number of bytes written to buffer
 */
static ssize_t temperature_show(struct device *dev,
                                struct device_attribute *attr, char *buf) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  int temp;

  mutex_lock(&sensor->lock);
  temp = sensor->current_temp;
  mutex_unlock(&sensor->lock);

  return sprintf(buf, "%d\n", temp);
}

/**
 * temperature_store - Set current temperature
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer containing temperature string
 * @count: Size of buffer
 *
 * Return: Number of bytes processed on success, negative error code on failure
 */
static ssize_t temperature_store(struct device *dev,
                                 struct device_attribute *attr, const char *buf,
                                 size_t count) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  int temp;
  int ret;

  ret = kstrtoint(buf, 10, &temp);
  if (ret) {
    sensor->stats_last_error = ret;
    return ret;
  }

  if (temp < MIN_TEMP || temp > MAX_TEMP) {
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  mutex_lock(&sensor->lock);
  sensor->current_temp = temp;
  sensor->stats_updates++;

  /* Reset ramp base when temperature is manually set */
  if (sensor->mode == MODE_RAMP) {
    sensor->ramp_base_temp = temp;
  }

  /* Notify clients */
  struct nxp_simtemp_client *client;
  list_for_each_entry(client, &sensor->client_list, node) {
    nxp_simtemp_generate_sample(sensor, client);
    client->data_available = true;
    client->last_temp = temp;
  }
  wake_up_interruptible(&sensor->read_queue);

  if (sensor->tzd)
    thermal_zone_device_update(sensor->tzd, THERMAL_EVENT_UNSPECIFIED);

  mutex_unlock(&sensor->lock);

  return count;
}

/**
 * monitoring_show - Show monitoring status
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer to store monitoring status string
 *
 * Return: Number of bytes written to buffer
 */
static ssize_t monitoring_show(struct device *dev,
                               struct device_attribute *attr, char *buf) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  bool active;

  mutex_lock(&sensor->lock);
  active = sensor->monitoring_active;
  mutex_unlock(&sensor->lock);

  return sprintf(buf, "%d\n", active);
}

/**
 * monitoring_store - Set monitoring status
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer containing monitoring status string
 * @count: Size of buffer
 *
 * Return: Number of bytes processed on success, negative error code on failure
 */
static ssize_t monitoring_store(struct device *dev,
                                struct device_attribute *attr, const char *buf,
                                size_t count) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  bool active;
  int ret;

  ret = kstrtobool(buf, &active);
  if (ret) {
    sensor->stats_last_error = ret;
    return ret;
  }

  mutex_lock(&sensor->lock);
  sensor->monitoring_active = active;
  mutex_unlock(&sensor->lock);

  return count;
}

/**
 * sampling_show - Show sampling interval
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer to store sampling interval string
 *
 * Return: Number of bytes written to buffer
 */
static ssize_t sampling_show(struct device *dev, struct device_attribute *attr,
                             char *buf) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  int sampling_ms;

  mutex_lock(&sensor->lock);
  sampling_ms = sensor->polling_interval;
  mutex_unlock(&sensor->lock);

  return sprintf(buf, "%d\n", sampling_ms);
}

/**
 * sampling_store - Set sampling interval
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer containing sampling interval string
 * @count: Size of buffer
 *
 * Return: Number of bytes processed on success, negative error code on failure
 */
static ssize_t sampling_store(struct device *dev, struct device_attribute *attr,
                              const char *buf, size_t count) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  int sampling_ms;
  int ret;

  ret = kstrtoint(buf, 10, &sampling_ms);
  if (ret) {
    sensor->stats_last_error = ret;
    return ret;
  }

  if (sampling_ms < SAMPLING_MIN || sampling_ms > SAMPLING_MAX) {
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  mutex_lock(&sensor->lock);
  sensor->polling_interval = sampling_ms;
  mutex_unlock(&sensor->lock);

  return count;
}

/**
 * threshold_mC_show - Show trip point thresholds
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer to store threshold information
 *
 * Return: Number of bytes written to buffer
 */
static ssize_t threshold_mC_show(struct device *dev,
                                 struct device_attribute *attr, char *buf) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  ssize_t count = 0;
  int i;

  mutex_lock(&sensor->lock);

  for (i = 0; i < TRIP_POINTS; i++) {
    if (sensor->trip_points[i] != 0 || i < sensor->num_trip_points) {
      count += sprintf(buf + count, "%d %d %d\n", i, sensor->trip_points[i],
                       sensor->trip_types[i]);
    }
  }

  mutex_unlock(&sensor->lock);

  return count;
}

/**
 * threshold_mC_store - Set trip point threshold
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer containing threshold information
 * @count: Size of buffer
 *
 * Return: Number of bytes processed on success, negative error code on failure
 */
static ssize_t threshold_mC_store(struct device *dev,
                                  struct device_attribute *attr,
                                  const char *buf, size_t count) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  int index, temp_mC, type;
  int ret;

  ret = sscanf(buf, "%d %d %d", &index, &temp_mC, &type);
  if (ret != 3) {
    dev_err(dev, "Invalid format. Use: index temperature_mC type\n");
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  if (index < 0 || index >= TRIP_POINTS) {
    dev_err(dev, "Invalid trip point index: %d (must be 0-%d)\n", index,
            TRIP_POINTS - 1);
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  if (temp_mC < MIN_TEMP || temp_mC > MAX_TEMP) {
    dev_err(dev, "Invalid temperature: %d (must be %d to %d)\n", temp_mC,
            MIN_TEMP, MAX_TEMP);
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  if (type < THERMAL_TRIP_ACTIVE || type > THERMAL_TRIP_CRITICAL) {
    dev_err(dev, "Invalid trip type: %d (must be %d to %d)\n", type,
            THERMAL_TRIP_ACTIVE, THERMAL_TRIP_CRITICAL);
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  mutex_lock(&sensor->lock);

  sensor->trip_points[index] = temp_mC;
  sensor->trip_types[index] = type;

  if (index >= sensor->num_trip_points && temp_mC != 0) {
    sensor->num_trip_points = index + 1;
  }

  if (sensor->trips && index < TRIP_POINTS) {
    sensor->trips[index].temperature = temp_mC;
    sensor->trips[index].type = type;
  }

  if (sensor->tzd) {
    thermal_zone_device_update(sensor->tzd, THERMAL_EVENT_UNSPECIFIED);
  }

  dev_info(dev, "Trip point %d set to %d mC with type %d\n", index, temp_mC,
           type);

  mutex_unlock(&sensor->lock);

  return count;
}

/**
 * mode_show - Show current operation mode
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer to store mode string
 *
 * Return: Number of bytes written to buffer
 */
static ssize_t mode_show(struct device *dev, struct device_attribute *attr,
                         char *buf) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  enum nxp_simtemp_mode mode;

  mutex_lock(&sensor->lock);
  mode = sensor->mode;
  mutex_unlock(&sensor->lock);

  if (mode >= MODE_MAX)
    return sprintf(buf, "unknown\n");

  return sprintf(buf, "%s\n", mode_names[mode]);
}

/**
 * mode_store - Set operation mode
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer containing mode string
 * @count: Size of buffer
 *
 * Return: Number of bytes processed on success, negative error code on failure
 */
static ssize_t mode_store(struct device *dev, struct device_attribute *attr,
                          const char *buf, size_t count) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  enum nxp_simtemp_mode new_mode;
  int i;

  /* Find matching mode */
  for (i = 0; i < MODE_MAX; i++) {
    if (sysfs_streq(buf, mode_names[i])) {
      new_mode = i;
      break;
    }
  }

  if (i == MODE_MAX) {
    dev_err(dev, "Invalid mode: %s (valid modes: normal, noisy, ramp)\n", buf);
    sensor->stats_last_error = -EINVAL;
    return -EINVAL;
  }

  mutex_lock(&sensor->lock);
  sensor->mode = new_mode;

  /* Initialize mode-specific state */
  switch (new_mode) {
  case MODE_RAMP:
    /* Initialize ramp mode state */
    sensor->ramp_direction = 1;
    sensor->ramp_base_temp = sensor->current_temp;
    break;
  case MODE_NORMAL:
  case MODE_NOISY:
    /* Reset ramp state when switching to other modes */
    sensor->ramp_direction = 0;
    sensor->ramp_base_temp = 0;
    break;
  default:
    break;
  }

  dev_info(dev, "Operation mode changed to: %s\n", mode_names[new_mode]);
  mutex_unlock(&sensor->lock);

  return count;
}

/**
 * stats_show - Show device statistics
 * @dev: Device structure
 * @attr: Device attribute
 * @buf: Buffer to store statistics string
 *
 * Return: Number of bytes written to buffer
 */
static ssize_t stats_show(struct device *dev, struct device_attribute *attr,
                          char *buf) {
  struct nxp_simtemp_dev *sensor = dev_get_drvdata(dev);
  unsigned long updates, alerts;
  int last_error;

  mutex_lock(&sensor->lock);
  updates = sensor->stats_updates;
  alerts = sensor->stats_alerts;
  last_error = sensor->stats_last_error;
  mutex_unlock(&sensor->lock);

  return sprintf(buf, "updates: %lu\nalerts: %lu\nlast_error: %d\n", updates,
                 alerts, last_error);
}

static DEVICE_ATTR_RW(temperature);
static DEVICE_ATTR_RW(monitoring);
static DEVICE_ATTR_RW(sampling);
static DEVICE_ATTR_RW(threshold_mC);
static DEVICE_ATTR_RW(mode);
static DEVICE_ATTR_RO(stats);

static struct attribute *nxp_simtemp_attrs[] = {
    &dev_attr_temperature.attr,
    &dev_attr_monitoring.attr,
    &dev_attr_sampling.attr,
    &dev_attr_threshold_mC.attr,
    &dev_attr_mode.attr,
    &dev_attr_stats.attr,
    NULL,
};

static const struct attribute_group nxp_simtemp_attr_group = {
    .attrs = nxp_simtemp_attrs,
};

/**
 * nxp_simtemp_probe - Platform device probe function
 * @pdev: Platform device structure
 *
 * Initializes the simulated temperature sensor device, sets up character
 * device interface, thermal zone, and monitoring thread.
 *
 * Return: 0 on success, negative error code on failure
 */
static int nxp_simtemp_probe(struct platform_device *pdev) {
  struct nxp_simtemp_dev *dev;
  struct device *device = &pdev->dev;
  int ret;
  int i;

  printk(KERN_INFO "NXP_SIMTEMP: Probe function called\n");

  dev = devm_kzalloc(device, sizeof(*dev), GFP_KERNEL);
  if (!dev)
    return -ENOMEM;

  platform_set_drvdata(pdev, dev);
  dev->device = device;

  mutex_init(&dev->lock);
  INIT_LIST_HEAD(&dev->client_list);
  init_waitqueue_head(&dev->read_queue);

  dev->current_temp = DEFAULT_TEMP;
  dev->monitoring_active = false;
  dev->polling_interval = 2000;

  /* Initialize mode and statistics */
  dev->mode = MODE_NORMAL;
  dev->stats_updates = 0;
  dev->stats_alerts = 0;
  dev->stats_last_error = 0;
  dev->ramp_direction = 0;
  dev->ramp_base_temp = 0;

  for (i = 0; i < TRIP_POINTS; i++) {
    dev->trip_points[i] = 0;
    dev->trip_types[i] = THERMAL_TRIP_ACTIVE;
  }
  dev->trip_points[0] = 50000;
  dev->trip_types[0] = THERMAL_TRIP_PASSIVE;
  dev->num_trip_points = 1;

  if (device->of_node) {
    of_property_read_u32(device->of_node, "nxp,initial-temperature",
                         &dev->current_temp);
    of_property_read_u32(device->of_node, "nxp,polling-interval-ms",
                         &dev->polling_interval);
  }

  ret = alloc_chrdev_region(&dev->devno, 0, 1, DRIVER_NAME);
  if (ret < 0) {
    dev_err(device, "Failed to allocate char device region\n");
    return ret;
  }

  cdev_init(&dev->cdev, &nxp_simtemp_fops);
  dev->cdev.owner = THIS_MODULE;

  ret = cdev_add(&dev->cdev, dev->devno, 1);
  if (ret < 0) {
    dev_err(device, "Failed to add char device\n");
    goto err_cdev;
  }

  dev->class = class_create(DRIVER_NAME);
  if (IS_ERR(dev->class)) {
    ret = PTR_ERR(dev->class);
    goto err_class;
  }

  dev->device = device_create(dev->class, device, dev->devno, NULL, "simtemp");
  if (IS_ERR(dev->device)) {
    ret = PTR_ERR(dev->device);
    goto err_device;
  }

  ret = sysfs_create_group(&device->kobj, &nxp_simtemp_attr_group);
  if (ret) {
    dev_err(device, "Failed to create sysfs attributes\n");
    goto err_sysfs;
  }

  dev->trips = devm_kcalloc(device, dev->num_trip_points,
                            sizeof(struct thermal_trip), GFP_KERNEL);
  if (!dev->trips) {
    ret = -ENOMEM;
    goto err_trips;
  }

  for (i = 0; i < dev->num_trip_points; i++) {
    dev->trips[i].temperature = dev->trip_points[i];
    dev->trips[i].type = dev->trip_types[i];
  }

  dev->tzd = thermal_zone_device_register_with_trips(
      "nxp_simtemp", dev->trips, dev->num_trip_points, 0, dev,
      &nxp_simtemp_thermal_ops, NULL, 0, dev->polling_interval);
  if (IS_ERR(dev->tzd)) {
    dev_err(device, "Failed to register thermal zone\n");
    ret = PTR_ERR(dev->tzd);
    goto err_thermal;
  }

  dev->thread_running = true;
  dev->monitor_thread =
      kthread_run(nxp_simtemp_monitor_thread, dev, "nxp_simtemp_monitor");
  if (IS_ERR(dev->monitor_thread)) {
    dev_err(device, "Failed to start monitor thread\n");
    ret = PTR_ERR(dev->monitor_thread);
    goto err_thread;
  }

  dev_info(device, "NXP Simulated Temperature Sensor initialized\n");
  dev_info(device, "Initial temperature: %d°C\n", dev->current_temp / 1000);
  dev_info(device, "Initial mode: %s\n", mode_names[dev->mode]);

  return 0;

err_thread:
  thermal_zone_device_unregister(dev->tzd);
err_thermal:
err_trips:
  sysfs_remove_group(&device->kobj, &nxp_simtemp_attr_group);
err_sysfs:
  device_destroy(dev->class, dev->devno);
err_device:
  class_destroy(dev->class);
err_class:
  cdev_del(&dev->cdev);
err_cdev:
  unregister_chrdev_region(dev->devno, 1);
  return ret;
}

/**
 * nxp_simtemp_remove - Platform device remove function
 * @pdev: Platform device structure
 *
 * Cleans up device resources, stops monitoring thread, and unregisters
 * thermal zone and character device.
 *
 * Return: 0 on success
 */
static int nxp_simtemp_remove(struct platform_device *pdev) {
  struct nxp_simtemp_dev *dev = platform_get_drvdata(pdev);

  printk(KERN_INFO "NXP_SIMTEMP: Remove function called\n");

  if (dev->monitor_thread) {
    dev->thread_running = false;
    kthread_stop(dev->monitor_thread);
  }

  if (dev->tzd)
    thermal_zone_device_unregister(dev->tzd);

  sysfs_remove_group(&pdev->dev.kobj, &nxp_simtemp_attr_group);
  device_destroy(dev->class, dev->devno);
  class_destroy(dev->class);
  cdev_del(&dev->cdev);
  unregister_chrdev_region(dev->devno, 1);

  dev_info(&pdev->dev, "NXP Simulated Temperature Sensor removed\n");

  return 0;
}

static const struct of_device_id nxp_simtemp_of_match[] = {
    {
        .compatible = "nxp,simtemp",
    },
    {},
};
MODULE_DEVICE_TABLE(of, nxp_simtemp_of_match);

static struct platform_driver nxp_simtemp_driver = {
    .probe = nxp_simtemp_probe,
    .remove = nxp_simtemp_remove,
    .driver =
        {
            .name = DRIVER_NAME,
            .of_match_table = nxp_simtemp_of_match,
        },
};

module_platform_driver(nxp_simtemp_driver);

MODULE_AUTHOR("Arturo Plauchu");
MODULE_DESCRIPTION("NXP Simulated Temperature Sensor Driver");
MODULE_LICENSE("GPL");
MODULE_VERSION("1.0");
