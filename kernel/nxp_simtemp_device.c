#include <linux/module.h>
#include <linux/platform_device.h>

/**
 * nxp_simtemp_device_release - Device release callback function
 * @dev: Platform device structure being released
 *
 * This function is called when the platform device's reference count
 * reaches zero and the device is being removed from the system.
 * It performs any necessary cleanup operations before the device
 * is completely destroyed.
 *
 * Context: May be called in process context during device removal
 */
static void nxp_simtemp_device_release(struct device *dev) {
  printk(KERN_INFO "nxp_simtemp device released\n");
}

/**
 * nxp_simtemp_device - Platform device structure for NXP simulated temperature
   sensor
 *
 * This structure defines the platform device that will be registered
 * with the kernel. It provides the necessary information for the
 * platform subsystem to manage the device.
 *
 * The structure contains:
 * - Device name for identification
 * - ID for device instance (-1 for single instance)
 * - Device operations including release callback
 */
static struct platform_device nxp_simtemp_device = {
    .name = "nxp_simtemp", /* Device name used for driver matching */
    .id = -1,              /* Single instance device */
    .dev =
        {
            .release = nxp_simtemp_device_release, /* Cleanup callback */
        },
};

/**
 * nxp_simtemp_device_init - Platform device initialization function
 *
 * Registers the NXP simulated temperature sensor platform device
 * with the kernel's platform subsystem. This makes the device
 * available for the platform driver to bind to.
 *
 * The function:
 * - Prints initialization debug information
 * - Registers the platform device
 * - Handles registration errors gracefully
 * - Provides success/failure status messages
 *
 * Return: 0 on success, negative error code on failure
 *
 * Context: Process context during module initialization
 */
static int __init nxp_simtemp_device_init(void) {
  int ret;

  printk(KERN_INFO "Registering nxp_simtemp platform device\n");
  ret = platform_device_register(&nxp_simtemp_device);
  if (ret) {
    printk(KERN_ERR "Failed to register platform device: %d\n", ret);
    return ret;
  }

  printk(KERN_INFO "nxp_simtemp platform device registered successfully\n");
  return 0;
}

/**
 * nxp_simtemp_device_exit - Platform device cleanup function
 *
 * Unregisters the NXP simulated temperature sensor platform device
 * from the kernel's platform subsystem. This removes the device
 * from the system and triggers the release callback for cleanup.
 *
 * The function:
 * - Unregisters the platform device
 * - Prints cleanup debug information
 * - Ensures proper device removal
 *
 * Context: Process context during module removal
 */
static void __exit nxp_simtemp_device_exit(void) {
  platform_device_unregister(&nxp_simtemp_device);
  printk(KERN_INFO "nxp_simtemp platform device unregistered\n");
}

/* Module initialization and exit points */
module_init(nxp_simtemp_device_init);
module_exit(nxp_simtemp_device_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Arturo Plauchu");
MODULE_DESCRIPTION("NXP Simulated Temperature Sensor Platform Device");
MODULE_VERSION("1.0");
