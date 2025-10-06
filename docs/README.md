# NXP Simulated Temperature

NXP Simulated Temperature Sensor kernel driver.

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


### 3. For GUI there are two options:

#### a) Install using Poetry
```bash
sudo apt install -y python3-dev build-essential
sudo apt install -y qt5-default qtbase5-dev qttools5-dev-tools
sudo apt install -y libqt5svg5-dev qtdeclarative5-dev

cd ../user/gui

poetry install

# if PyQT5 poetry install failed try:
poetry run pip3 install PyQt5==5.15.10
# If failed it is possible PyQt5 is not available for your platform or arch
```
##### Once completed you can run CLI
```bash
poetry run task nxp_simtemp_gui

```
#### b) Install using Standalone python
```bash

sudo apt install -y python3-dev build-essential
sudo apt install -y qt5-default qtbase5-dev qttools5-dev-tools
sudo apt install -y libqt5svg5-dev qtdeclarative5-dev
# For PyQt5 specifically
sudo apt install -y pyqt5-dev pyqt5-dev-tools python3-pyqt5

```
```bash
cd ../user/cli
pip3 install -r requirements.txt

```
##### Once completed you can run GUI
```bash
cd ../user/gui
./main.py
```

### For more instruction read user/cli/README.md
