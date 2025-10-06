#!/bin/bash

# Lint script for nxm_simptemp driver
# Runs checkpatch.pl and clang-format checks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRIVER_NAME="nxm_simptemp"
DRIVER_PATH="."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKPATCH_PATH="${CHECKPATCH_PATH:-scripts/checkpatch.pl}"
CLANG_FORMAT="${CLANG_FORMAT:-clang-format}"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to find source files
find_source_files() {
    local search_path="$1"
    if [[ -d "$search_path" ]]; then
        find "$search_path" -name "*.c" -o -name "*.h" | grep -vE "(build|\.git)"
    elif [[ -f "$search_path" ]]; then
        # Single file provided
        echo "$search_path"
    else
        # Try to find files matching driver name
        find . -name "*.c" -o -name "*.h" | grep -E "(/${DRIVER_NAME}|${DRIVER_NAME}\.)" | grep -vE "(build|\.git)"
    fi
}

# Function to validate driver path
validate_driver_path() {
    local path="$1"
    
    if [[ -f "$path" ]]; then
        # It's a single file
        if [[ "$path" =~ \.(c|h)$ ]]; then
            return 0
        else
            print_error "File $path is not a C source file (.c or .h)"
            return 1
        fi
    elif [[ -d "$path" ]]; then
        # It's a directory
        local files=$(find "$path" -name "*.c" -o -name "*.h" 2>/dev/null | head -1)
        if [[ -n "$files" ]]; then
            return 0
        else
            print_error "Directory $path contains no C source files (.c or .h)"
            return 1
        fi
    else
        print_error "Path $path does not exist"
        return 1
    fi
}

# Function to run checkpatch.pl
run_checkpatch() {
    local files
    files=$(find_source_files "$DRIVER_PATH")
    
    if [[ -z "$files" ]]; then
        print_error "No source files found at: $DRIVER_PATH"
        return 1
    fi

    ln -sf /usr/src/linux-headers-$(uname -r)/scripts/checkpatch.pl $(pwd)/checkpatch.pl
    
    print_info "Running checkpatch.pl on: $DRIVER_PATH"
    
    if [[ ! -f "$CHECKPATCH_PATH" ]]; then
        print_warning "checkpatch.pl not found at $CHECKPATCH_PATH"
        print_info "Trying to find checkpatch.pl in common locations..."
        
        # Try common locations
        if [[ -f "scripts/checkpatch.pl" ]]; then
            CHECKPATCH_PATH="scripts/checkpatch.pl"
        elif [[ -f "../scripts/checkpatch.pl" ]]; then
            CHECKPATCH_PATH="../scripts/checkpatch.pl"
        elif command_exists checkpatch.pl; then
            CHECKPATCH_PATH="checkpatch.pl"
        else
            print_error "checkpatch.pl not found. Please install it or set CHECKPATCH_PATH environment variable"
            return 1
        fi
    fi
    
    local errors=0
    local file_count=0
    
    for file in $files; do
        if [[ ! -f "$file" ]]; then
            continue
        fi
        print_info "Checking: $file"
        if ! perl "$CHECKPATCH_PATH" --no-tree -f "$file" 2>/dev/null; then
            ((errors++))
        fi
        ((file_count++))
    done
    
    if [[ $file_count -eq 0 ]]; then
        print_error "No valid source files found to check"
        return 1
    fi
    
    if [[ $errors -eq 0 ]]; then
        print_success "checkpatch.pl passed for all $file_count file(s)"
    else
        print_error "checkpatch.pl found issues in $errors out of $file_count file(s)"
        return 1
    fi
}

# Function to run clang-format check
run_clang_format() {
    local files
    files=$(find_source_files "$DRIVER_PATH")
    
    if [[ -z "$files" ]]; then
        print_error "No source files found at: $DRIVER_PATH"
        return 1
    fi
    
    if ! command_exists "$CLANG_FORMAT"; then
        print_error "clang-format not found. Please install it"
        return 1
    fi
    
    print_info "Running clang-format check on: $DRIVER_PATH"
    
    local errors=0
    local file_count=0
    
    for file in $files; do
        if [[ ! -f "$file" ]]; then
            continue
        fi
        print_info "Checking format: $file"
        if ! "$CLANG_FORMAT" --dry-run --Werror "$file" >/dev/null 2>&1; then
            print_error "Formatting issues in: $file"
            print_info "Suggested changes:"
            "$CLANG_FORMAT" "$file" | diff -u "$file" - || true
            ((errors++))
        fi
        ((file_count++))
    done
    
    if [[ $file_count -eq 0 ]]; then
        print_error "No valid source files found to check"
        return 1
    fi
    
    if [[ $errors -eq 0 ]]; then
        print_success "clang-format passed for all $file_count file(s)"
    else
        print_error "clang-format found issues in $errors out of $file_count file(s)"
        print_info "You can fix formatting with: $CLANG_FORMAT -i [file]"
        return 1
    fi
}

# Function to fix clang-format issues
fix_clang_format() {
    local files
    files=$(find_source_files "$DRIVER_PATH")
    
    if [[ -z "$files" ]]; then
        print_error "No source files found at: $DRIVER_PATH"
        return 1
    fi
    
    if ! command_exists "$CLANG_FORMAT"; then
        print_error "clang-format not found. Please install it"
        return 1
    fi
    
    print_info "Fixing clang-format issues for: $DRIVER_PATH"
    
    local file_count=0
    for file in $files; do
        if [[ ! -f "$file" ]]; then
            continue
        fi
        print_info "Fixing format: $file"
        "$CLANG_FORMAT" -i "$file"
        ((file_count++))
    done
    
    if [[ $file_count -eq 0 ]]; then
        print_error "No valid source files found to fix"
        return 1
    fi
    
    print_success "clang-format fixes applied to $file_count file(s)"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Lint script for nxm_simptemp driver"
    echo ""
    echo "OPTIONS:"
    echo "  -c, --checkpatch    Run only checkpatch.pl"
    echo "  -f, --clang-format  Run only clang-format check"
    echo "  --fix-format        Fix clang-format issues automatically"
    echo "  -d, --driver NAME   Specify driver name (default: nxm_simptemp)"
    echo "  -p, --path PATH     Specify path to driver files or directory (default: .)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 -p drivers/thermal/nxm_simptemp/"
    echo "  $0 -p nxm_simptemp.c"
    echo "  $0 -p src/ -d nxm_simptemp"
    echo ""
    echo "ENVIRONMENT VARIABLES:"
    echo "  CHECKPATCH_PATH     Path to checkpatch.pl (default: scripts/checkpatch.pl)"
    echo "  CLANG_FORMAT        clang-format command (default: clang-format)"
}

# Parse command line arguments
RUN_CHECKPATCH=true
RUN_CLANG_FORMAT=true
FIX_FORMAT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--checkpatch)
            RUN_CLANG_FORMAT=false
            shift
            ;;
        -f|--clang-format)
            RUN_CHECKPATCH=false
            shift
            ;;
        --fix-format)
            FIX_FORMAT=true
            RUN_CHECKPATCH=false
            shift
            ;;
        -d|--driver)
            DRIVER_NAME="$2"
            shift 2
            ;;
        -p|--path)
            DRIVER_PATH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

main() {
    print_info "Starting lint checks"
    print_info "Driver: $DRIVER_NAME"
    print_info "Path: $DRIVER_PATH"
    
    # Validate driver path
    if ! validate_driver_path "$DRIVER_PATH"; then
        exit 1
    fi
    
    # Change to script directory (but store original for relative paths)
    cd "$SCRIPT_DIR"
    
    # If DRIVER_PATH is relative, make sure we can still find it
    if [[ ! -e "$DRIVER_PATH" && -e "$SCRIPT_DIR/$DRIVER_PATH" ]]; then
        DRIVER_PATH="$SCRIPT_DIR/$DRIVER_PATH"
    fi
    
    local exit_code=0
    
    # Run checkpatch if requested
    if [[ "$RUN_CHECKPATCH" == true ]]; then
        if ! run_checkpatch; then
            exit_code=1
        fi
    fi
    
    # Run clang-format check or fix
    if [[ "$FIX_FORMAT" == true ]]; then
        if ! fix_clang_format; then
            exit_code=1
        fi
    elif [[ "$RUN_CLANG_FORMAT" == true ]]; then
        if ! run_clang_format; then
            exit_code=1
        fi
    fi
    
    if [[ $exit_code -eq 0 ]]; then
        print_success "All lint checks passed!"
    else
        print_error "Some lint checks failed"
    fi
    
    exit $exit_code
}

# Run main function
main