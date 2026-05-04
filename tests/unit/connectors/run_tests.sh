#!/bin/bash
# Connector Unit Tests Runner
# Usage: ./run_tests.sh [options]

set -e

echo "🧪 Drug Designer Connector Unit Tests"
echo "======================================"
echo ""

# Default options
VERBOSE="-v"
COVERAGE=""
PARALLEL=""
FILTER=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE="--cov=apps/api/connectors --cov-report=html --cov-report=term-missing"
            shift
            ;;
        --parallel)
            PARALLEL="-n auto"
            shift
            ;;
        --filter)
            FILTER="-k $2"
            shift 2
            ;;
        --quiet)
            VERBOSE="-q"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run tests
echo "Running connector unit tests..."
echo ""

pytest tests/unit/connectors/ $VERBOSE $COVERAGE $PARALLEL $FILTER

echo ""
echo "✅ Test run complete!"

if [ -n "$COVERAGE" ]; then
    echo ""
    echo "📊 Coverage report generated: htmlcov/index.html"
fi
