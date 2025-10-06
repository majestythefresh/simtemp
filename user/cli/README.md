# NXP Simulated Temperature Sensor CLI Tool

A command-line interface for interacting with the NXP Simulated Temperature Sensor kernel driver.

## Installation


### 1. Install Driver using the proper compiler and ARCH
```bash
cd ../scripts

./build.sh --driver "ARCH=arm64 CC=aarch64-linux-gnu-gcc"

```
##### Once completed udev rules is installed and .ko modules loaded

### 2. For Cli there are two options:

#### a) Install using Poetry
```bash
cd ../scripts

./build.sh --poetry
```
##### Once completed you can run CLI
```bash
cd ../user/cli

poetry run task nxp_simtemp [command] [options]

poetry run task nxp_simtemp --help
```
#### b) Install using Standalone python
```bash
cd ../user/cli
pip3 install -r requirements.txt

```

```bash
cd ../user/scripts

./build.sh --standalone
```
##### Once completed you can run CLI
```bash
nxp_simtemp [command] [options]
nxp_simtemp --help
```

## Cleaning

### 1. Clean Driver
```bash
cd ../user/scripts

./build.sh --clean-driver
```
### 2. For Cli there are three options:

#### a) Cleaning Poetry env
```bash
cd ../scripts

./build.sh --clean-poetry
```
#### b) Cleaning Standalone python
```bash
cd ../scripts

./build.sh --clean-standalone
```
#### c) Cleaning All
```bash
cd ../scripts

./build.sh --clean-all
```

