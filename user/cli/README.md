# NXP Simulated Temperature Sensor CLI Tool

A command-line interface for interacting with the NXP Simulated Temperature Sensor kernel driver.

## Installation


### 1. Install Driver using the proper compiler and ARCH
```bash
cd ../user/cli

./build.sh --driver "ARCH=arm64 CC=aarch64-linux-gnu-gcc"
```
### 2. For Cli there are two options:

#### a) Install using Poetry
```bash
cd ../user/cli

./build.sh --poetry
```
##### Once completed you can run CLI
```bash
poetry run task nxp_simtemp [command] [options]

poetry run task nxp_simtemp --help
```
#### b) Install using Standalone python
```bash
cd ../user/cli

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
cd ../user/cli

./build.sh --clean-driver
```
### 2. For Cli there are three options:

#### a) Cleaning Poetry env
```bash
cd ../user/cli

./build.sh --clean-poetry
```
#### b) Cleaning Standalone python
```bash
cd ../user/cli

./build.sh --clean-standalone
```
#### c) Cleaning All
```bash
cd ../user/cli

./build.sh --clean-all
```

