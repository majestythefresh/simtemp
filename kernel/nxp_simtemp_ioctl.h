/* SPDX-License-Identifier: GPL-2.0 */
/*
 * NXP Simulated Temperature Sensor Driver - IOCTL Definitions
 *
 * Contains IOCTL command definitions and related structures for
 * user-space communication with the NXP simulated temperature sensor.
 */

#ifndef _NXP_SIMTEMP_IOCTL_H_
#define _NXP_SIMTEMP_IOCTL_H_

#include <linux/ioctl.h>
#include <linux/types.h>

/* IOCTL magic number */
#define NXP_SIMTEMP_MAGIC 'T'

/* IOCTL commands */
#define NXP_SIMTEMP_SET_TEMP _IOW(NXP_SIMTEMP_MAGIC, 1, int)
#define NXP_SIMTEMP_GET_TEMP _IOR(NXP_SIMTEMP_MAGIC, 2, int)
#define NXP_SIMTEMP_SET_TRIP _IOW(NXP_SIMTEMP_MAGIC, 3, int[3])
#define NXP_SIMTEMP_GET_TRIP _IOR(NXP_SIMTEMP_MAGIC, 4, int[3])
#define NXP_SIMTEMP_START_MONITOR _IO(NXP_SIMTEMP_MAGIC, 5)
#define NXP_SIMTEMP_STOP_MONITOR _IO(NXP_SIMTEMP_MAGIC, 6)

#endif /* _NXP_SIMTEMP_IOCTL_H_ */
