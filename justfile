# Default Python versions and backends to test
default_pythons := "3.10 3.14"
default_backends := "PySide6 PyQt6"
default_resolutions := "lowest-direct highest"

# Run matrix tests with optional python versions, backends, and resolutions
# Usage: just test-matrix [pythons] [backends] [resolutions]
# Example: just test-matrix "3.10 3.12 3.14" "PySide6" "lowest-direct"
test-matrix pythons=default_pythons backends=default_backends resolutions=default_resolutions:
    #!/usr/bin/env bash
    set -euo pipefail

    # Colors for output
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    BLUE='\033[0;34m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color

    # Arrays to track results
    declare -a failed_tests
    declare -a passed_tests
    total=0
    failed=0

    # Split pythons, backends, and resolutions into arrays
    IFS=' ' read -ra PYTHON_VERSIONS <<< "{{pythons}}"
    IFS=' ' read -ra BACKENDS <<< "{{backends}}"
    IFS=' ' read -ra RESOLUTIONS <<< "{{resolutions}}"

    # Detect number of performance cores (macOS) or fall back to physical cores
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: use performance cores only (excludes efficiency cores)
        NUM_CORES=$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || sysctl -n hw.physicalcpu)
    else
        NUM_CORES='auto'
    fi

    # Create a temporary directory for test environments
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT

    echo -e "${BLUE}Using temporary directory: ${TEMP_DIR}${NC}"

    # Iterate through matrix
    for py_version in "${PYTHON_VERSIONS[@]}"; do
        for backend in "${BACKENDS[@]}"; do
            for resolution in "${RESOLUTIONS[@]}"; do
                total=$((total + 1))
                test_name="py${py_version}-${backend}-${resolution}"
                venv_path="${TEMP_DIR}/.venv-${test_name}"

                echo -e "${YELLOW}================================================${NC}"
                echo -e "${BLUE}Testing: Python ${py_version} | ${backend} | ${resolution}${NC}"
                echo -e "${YELLOW}================================================${NC}"

                # Run tests with uv run (automatically creates and manages temp venv)
                # Set default pytest options (can be overridden via PYTEST_ADDOPTS)
                default_opts="-n ${NUM_CORES} --tb=short"
                if env -u VIRTUAL_ENV \
                   UV_PROJECT_ENVIRONMENT="${venv_path}" \
                   PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-$default_opts}" \
                   uv run \
                    --frozen \
                    --no-dev \
                    --python "${py_version}" \
                    --extra "${backend}" \
                    --group test \
                    --resolution "${resolution}" \
                    pytest --color=yes ; then
                    echo -e "${GREEN} Tests passed for Python ${py_version} | ${backend} | ${resolution}${NC}"
                    passed_tests+=("${test_name}")
                else
                    echo -e "${RED} Tests failed for Python ${py_version} | ${backend} | ${resolution}${NC}"
                    failed=$((failed + 1))
                    failed_tests+=("${test_name}: tests failed")
                fi

                echo ""
            done
        done
    done

    # Summary
    echo -e "${YELLOW}-----------------------------------------------${NC}"
    echo -e "${BLUE}Test Matrix Summary${NC}"
    echo -e "${YELLOW}-----------------------------------------------${NC}"
    echo ""
    echo "Total combinations tested: ${total}"
    echo "Passed: $((total - failed))"
    echo "Failed: ${failed}"
    echo ""

    if [ ${failed} -gt 0 ]; then
        echo -e "${RED}Failed tests:${NC}"
        for test in "${failed_tests[@]}"; do
            echo -e "  ${RED} ${test}${NC}"
        done
        for test in "${passed_tests[@]}"; do
            echo -e "  ${GREEN} ${test}${NC}"
        done
        echo ""
        exit 1
    else
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    fi

# Run tests for a specific Python version, backend, and resolution
# Usage: just test-single 3.11 PySide6 lowest-direct
test-single python backend="PyQt6" resolution="highest":
    @just test-matrix "{{python}}" "{{backend}}" "{{resolution}}"

# Test all pythons and backends with specific resolutions
# Usage: just test-resolutions "lowest-direct" or just test-resolutions "lowest-direct highest"
test-resolutions resolutions:
    @just test-matrix "{{default_pythons}}" "{{default_backends}}" "{{resolutions}}"

# Test specific pythons with all backends and resolutions
# Usage: just test-pythons "3.11 3.12"
test-pythons pythons:
    @just test-matrix "{{pythons}}" "{{default_backends}}" "{{default_resolutions}}"

# Test specific backends with all pythons and resolutions
# Usage: just test-backends "PySide6" or just test-backends "PySide6 PyQt6"
test-backends backends:
    @just test-matrix "{{default_pythons}}" "{{backends}}" "{{default_resolutions}}"
