#!/bin/bash
# Build and Installation script for NXP SimTemp CLI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_DIR="$SCRIPT_DIR/../user/cli"
INSTALL_DIR="/usr/local/bin"
BINARY_NAME="nxp_simtemp"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root"
        exit 1
    fi
}

# Check Python availability
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
}

# Check Poetry availability
check_poetry() {
    if command -v poetry &> /dev/null; then
        print_success "Poetry found: $(poetry --version)"
        return 0
    else
        print_warning "Poetry not found"
        return 1
    fi
}

# Check Poetry installed
check_poetry_env_exists() {
    cd $CLI_DIR
    if [[ $(poetry env list) == "" ]]; then
        print_warning "No Poetry environments found"
        return 0
    else
        print_warning "Poetry environments found"
        return 1 
    fi
}

# Create udev rules
setup_udev_rules() {
    print_info "Setting up udev rules for device permissions..."
    
    # Create udev rule for device permissions
    echo "Creating udev rules..."
cat << EOF | sudo tee /etc/udev/rules.d/99-nxp-simtemp.rules > /dev/null
# NXP Simulated Temperature Sensor permissions
KERNEL=="simtemp", SUBSYSTEM=="nxp_simtemp", MODE="0666"
# Sysfs files - use explicit path
SUBSYSTEM=="class", KERNEL=="nxp_simtemp", RUN+="/bin/chmod 0666 /sys/class/nxp_simtemp/simtemp/device/mode"
SUBSYSTEM=="class", KERNEL=="nxp_simtemp", RUN+="/bin/chmod 0666 /sys/class/nxp_simtemp/simtemp/device/temperature"
SUBSYSTEM=="class", KERNEL=="nxp_simtemp", RUN+="/bin/chmod 0666 /sys/class/nxp_simtemp/simtemp/device/sampling"
SUBSYSTEM=="class", KERNEL=="nxp_simtemp", RUN+="/bin/chmod 0666 /sys/class/nxp_simtemp/simtemp/device/monitoring"
SUBSYSTEM=="class", KERNEL=="nxp_simtemp", RUN+="/bin/chmod 0666 /sys/class/nxp_simtemp/simtemp/device/stats"
SUBSYSTEM=="class", KERNEL=="nxp_simtemp", RUN+="/bin/chmod 0666 /sys/class/nxp_simtemp/simtemp/device/threshold_mC"
EOF


    # Reload udev rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    print_success "Udev rules and sysfs permissions configured"
}

# Install Python standalone
install_python_standalone() {
    print_info "Installing Python standalone..."

    CLI_SCRIPT="$CLI_DIR/main.py"
    INSTALL_DIR="/usr/local/bin"

    echo "Installing NXP SimTemp CLI..."

    # Check Python version
    python3 --version >/dev/null 2>&1 || {
        echo "Error: Python 3 is required but not installed"
        exit 1
    }


    # Make script executable
    chmod +x "$CLI_SCRIPT"

    # Create symlink in install directory
    sudo ln -sf "$CLI_SCRIPT" "$INSTALL_DIR/nxp_simtemp"
    sudo ln -sf "$SCRIPT_DIR/../user/lib" "$INSTALL_DIR/lib"

    echo "Installation complete!"
    echo "Usage: nxp_simtemp [command] [options]"
    echo "Try: nxp_simtemp --help"
    
    print_success "Python standalone version installed"
}

# Clean Python standalone
clean_python_standalone() {
    print_info "Cleaning Python standalone..."

    if [ -f "$INSTALL_DIR/nxp_simtemp" ]; then
        sudo rm "$INSTALL_DIR/nxp_simtemp"
    fi

    echo ""
    print_success "Clean Python standalone complete!"
}

# Install with Poetry
install_poetry() {
    print_info "Installing with Poetry..."

    # Check if pyproject.toml exists
    if [[ ! -f "$CLI_DIR/pyproject.toml" ]]; then
        print_error "pyproject.toml not found in $CLI_DIR"
        print_info "Falling back to Python standalone installation"
        install_python_standalone
        return
    fi
    
    # Install dependencies
    cd "$CLI_DIR"
    poetry install
    echo ""
    echo "Installation complete!"
    echo "Enter to $CLI_DIR/"
    echo "   Usage: poetry run task nxp_simtemp [command] [options]"
    echo "   Try: poetry run task nxp_simtemp --help"
    print_success "Poetry version installed"
}

# Clean with Poetry
clean_poetry() {
    print_info "Cleaning Poetry..."

    # Install dependencies
    cd "$CLI_DIR"
    poetry env remove --all
    # Clear all caches
    poetry cache clear --all .
    # Remove lock file and reinstall from scratch
    rm poetry.lock
    rm -rf .venv/

    echo ""
    print_success "Clean Poetry environment complete!"
}

install_nxp_simtemp_driver() {
    local arch_cc="$1 $2"
    
    print_info "Installing NXP simtemp driver $arch_cc..."
    
    DRIVER_DIR="$SCRIPT_DIR/../kernel"
    
    # Check if driver directory exists
    if [ ! -d "$DRIVER_DIR" ]; then
        print_error "Driver directory not found: $DRIVER_DIR"
        return 1
    fi
    
    # Install dependencies and build
    cd "$DRIVER_DIR"
    
    print_info "Building driver with: $arch_cc"
    make $arch_cc all
    
    if [[ $? -eq 0 ]]; then
        print_success "Driver built successfully"
        
        # Remove existing modules if loaded
        sudo rmmod nxp_simtemp 2>/dev/null || true
        sudo rmmod nxp_simtemp_device 2>/dev/null || true
        
        # Load modules
        print_info "Loading kernel modules..."
        sudo insmod nxp_simtemp_device.ko
        sudo insmod nxp_simtemp.ko
        
        # Verify modules are loaded
        if lsmod | grep -q nxp_simtemp; then
            print_success "Driver loaded successfully"
        else
            print_error "Failed to load driver modules"
            return 1
        fi
    else
        print_error "Driver build failed"
        return 1
    fi
    
    echo ""
    print_success "NXP simtemp driver installation complete!"
    return 0
}

clean_nxp_simtemp_driver() {
    print_info "Cleaning NXP simtemp driver..."

    DRIVER_DIR="$SCRIPT_DIR/../kernel"
    # Install dependencies
    cd "$DRIVER_DIR"
    make clean
    sudo rmmod nxp_simtemp_device
    sudo rmmod nxp_simtemp

    echo ""
    print_success "Clean NXP simtemp driver complete!"
}

# Install dependencies
install_dependencies() {
    print_info "Installing system dependencies..."
    
    # Detect package manager
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip
    elif command -v yum &> /dev/null; then
        # RHEL/CentOS
        sudo yum install -y python3 python3-pip
    elif command -v dnf &> /dev/null; then
        # Fedora
        sudo dnf install -y python3 python3-pip
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        sudo pacman -S --noconfirm python python-pip
    else
        print_warning "Could not detect package manager, please ensure Python 3 is installed"
    fi
}


# Main installation function
main() {
    echo "========================================="
    echo "  NXP SimTemp CLI Installation Script"
    echo "========================================="
    echo ""
    
    if [[ $FORCE_METHOD == "poetry" ]]; then
        choice=1
    elif [[ $FORCE_METHOD == "standalone" ]]; then
        choice=2
     elif [[ $FORCE_METHOD == "driver" ]]; then
        choice=3
    elif [[ $FORCE_METHOD == "cpo" ]]; then
        choice=4
    elif [[ $FORCE_METHOD == "cst" ]]; then
        choice=5
    elif [[ $FORCE_METHOD == "cdr" ]]; then
        choice=6
    elif [[ $FORCE_METHOD == "clean" ]]; then
        choice=7
    elif [[ $FORCE_METHOD == "" ]]; then
        # Installation method selection
        echo ""
        echo "Select installation method:"
        echo "1) Poetry (recommended for development)"
        echo "2) Python standalone"
        echo "3) Compile and install nxp_simtemp driver"
        echo "4) Clean Poetry installation"
        echo "5) Clean Python standalone installation"
        echo "6) Clean Driver installation"
        echo "7) Clean All installation"
        echo ""
        read -p "Enter choice [1-7] (default: 3): " choice
    fi

    echo $chice
    if [[ $choice == 1 || $choice == 2 ]]; then

        # Pre-flight checks
        check_root
        check_python
        
        # Ask about dependencies
        read -p "Install system dependencies (Python 3, pip)? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_dependencies
        fi
        
        # Setup udev rules
        setup_udev_rules
    fi
    
    case $choice in
        1)
            if check_poetry; then
                install_poetry
            else
                print_error "Poetry selected but not available"
                exit 1
            fi
            ;;
        2)
            install_python_standalone
            ;;
        3)
            install_nxp_simtemp_driver $DRIVER_ARCH
            ;;
        
        4)
            check_poetry_env_exists
            if [[ $? == 1 ]]; then
                clean_poetry
            fi
            ;;
        5)
            clean_python_standalone
            ;;
        6)
            clean_nxp_simtemp_driver
            ;;
        7)
            check_poetry_env_exists
            if [[ $? == 1 ]]; then
                clean_poetry
            fi
            clean_python_standalone
            clean_nxp_simtemp_driver
            ;;
            
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
    
    echo ""
    
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help                         Show this help message"
    echo "  -p, --poetry                       Force Poetry installation"
    echo "  -s, --standalone                   Force Python standalone installation"
    echo "  -d, --driver "ARCH and CC string"  Force nxp simtemp driver installation"
    echo "  -cpo, --clean-poetry               Clean poetry installation"
    echo "  -cst, --clean-standalone           Clean poetry installation"
    echo "  -cdr, --clean-driver               Clean driver installation"
    echo "  -cla, --clean                      Clean all installations"
    echo ""
    echo "Examples:"
    echo "  $0                     # Interactive installation"
    echo "  $0 --poetry            # Force Poetry installation"
    echo "  $0 --standalone        # Force standalone installation"
    echo "  $0 --driver ""           # Force nxp simtemp driver installation with local compiler"
    echo "  $0 --driver \"ARCH=arm64 CC=aarch64-linux-gnu-gcc\"  
                                 # Force nxp simtemp driver installation with ARCH and CC compiler"
    echo "  $0 --clean-poetry      # Clean poetry installation"
    echo "  $0 --clean-standalone  # Clean poetry installation"
    echo "  $0 --clean-driver      # Clean driver installation"
    echo "  $0 --clean-all         # Clean installation"
}

# Parse command line arguments
FORCE_METHOD=""
DRIVER_ARCH=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--driver)
            if [[ -n "$2" && "$2" != -* ]]; then
                DRIVER_ARCH="$2"
                shift 2
            else
                DRIVER_ARCH=""  # Default or empty
                shift
            fi
            FORCE_METHOD="driver"
            ;;
        -p|--poetry)
            FORCE_METHOD="poetry"
            shift
            ;;
        -s|--standalone)
            FORCE_METHOD="standalone"
            shift
            ;;
        -cpo|--clean-poetry)
            FORCE_METHOD="cpo"
            shift
            ;;
        -cst|--clean-standalone)
            FORCE_METHOD="cst"
            shift
            ;;
        -cdr|--clean-driver)
            FORCE_METHOD="cdr"
            shift
            ;;
        -cla|--clean-all)
            FORCE_METHOD="clean"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function with error handling
if ! main; then
    print_error "Installation failed"
    exit 1
fi