# SPDX-License-Identifier: GPL-2.0
#
# Makefile for NXP Simulated Temperature Sensor Driver
#


# Normal makefile
obj-m += nxp_simtemp.o
obj-m += nxp_simtemp_device.o

# Kernel directory - adjust as needed
KERNELDIR ?= /lib/modules/$(shell uname -r)/build
PWD := $(shell pwd)

# Module installation directory
INSTALL_MOD_PATH ?= /
MODULE_INSTALL_DIR = $(INSTALL_MOD_PATH)/lib/modules/$(shell uname -r)/extra

# Compiler and flags
CC = $(CROSS_COMPILE)
CFLAGS = -Wall -Wextra -g

# Device Tree compiler
DTC = dtc
DTB_DIR = dts

# Source files
DRIVER_SRC = nxp_simtemp.c
DRIVER_OBJ = nxp_simtemp.o
MODULE = nxp_simtemp.ko

# Header files
DRIVER_HEADERS = nxp_simtemp.h nxp_simtemp_ioctl.h

# Device Tree sources
DTS_SRC = nxp-simtemp.dtsi
DTS_TEST_SRC = nxp_simtemp-test.dts
DTB = nxp_simtemp.dtb
DTB_TEST = nxp_simtemp-test.dtb

# Binding file
DT_BINDING = nxp,simtemp.yaml

# Default target
all: module dtb dt_validation

# Build the kernel module
module: $(DRIVER_HEADERS)
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules

# Compile Device Tree Blob
dtb:
	@if [ -f "dts/nxp-simtemp.dts" ]; then \
		echo "Building Device Tree Blobs..."; \
		dtc -I dts -O dtb -o dts/nxp_simtemp.dtb dts/nxp-simtemp.dts; \
		echo "DTBs built successfully"; \
	else \
		echo "Device Tree sources not found, skipping DTB build"; \
	fi

# Device Tree schema validation
dt_validation: $(DT_BINDING)
	@echo "Validating Device Tree binding..."
	@if command -v dt-validate >/dev/null 2>&1; then \
		dt-validate -s $(DT_BINDING) $(DTB_DIR)/$(DTS_SRC) || exit 1; \
		dt-validate -s $(DT_BINDING) $(DTB_DIR)/$(DTS_TEST_SRC) || exit 1; \
		echo "Device Tree validation passed"; \
	elif command -v dt_binding_check >/dev/null 2>&1; then \
		dt_binding_check -s $(DT_BINDING) $(DTB_DIR)/$(DTS_SRC) || exit 1; \
		dt_binding_check -s $(DT_BINDING) $(DTB_DIR)/$(DTS_TEST_SRC) || exit 1; \
		echo "Device Tree validation passed"; \
	else \
		echo "Warning: dt-validate or dt_binding_check not found, skipping validation"; \
	fi

# Install userspace headers
install_headers: $(DRIVER_HEADERS)
	@echo "Installing userspace headers..."
	@mkdir -p $(DESTDIR)/usr/include/linux
	@cp nxp_simtemp_ioctl.h $(DESTDIR)/usr/include/linux/
	@echo "Headers installed to $(DESTDIR)/usr/include/linux/"

# Kernel module installation
install: module install_headers
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules_install
	depmod -a

# Clean build artifacts
clean:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) clean
	rm -f nxp_simtemp_test
	rm -f $(DTB_DIR)/*.dtb
	rm -f *.o *.ko *.mod.c *.mod.o Module.symvers Module.markers modules.order
	rm -rf .tmp_versions
	rm -rf include

# Build for different architectures
arm64:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) ARCH=arm64 CC=aarch64-linux-gnu-gcc modules

arm:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) ARCH=arm CC=arm-linux-gnueabi-gcc modules

x86:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) ARCH=x86 CC=gcc modules

# Help target
help:
	@echo "Available targets:"
	@echo "  all              - Build module and DTB (default)"
	@echo "  module           - Build kernel module only"
	@echo "  install_headers  - Install userspace headers"
	@echo "  dtb              - Build Device Tree Blob"
	@echo "  dt_validation    - Validate Device Tree binding"
	@echo "  install          - Install module and headers system-wide"
	@echo "  clean            - Clean build artifacts"
	@echo "  arm64/arm/x86    - Build for specific architecture"
	@echo "  help             - Show this help message"

.PHONY: all module dtb dt_validation install install_headers clean arm64 arm x86 help