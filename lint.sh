#!/bin/bash
set -e

echo "Running code formatters and linters..."

# Check if running in CI mode (no fixes)
if [ "$1" = "ci" ]; then
    echo "Running in CI mode - checking only, not fixing..."
    uv run ruff format --check
    uv run ruff check
else
    uv run ruff format
    uv run ruff check --fix
fi

echo "Running type checker..."
# Pre-existing diagnostics are frozen in .basedpyright/baseline.json;
# only new issues fail. After fixing baselined ones, the baseline
# auto-shrinks; regenerate intentionally with: basedpyright --writebaseline
uv run basedpyright

echo "Checking architecture layer contract..."
# Layer order is defined in [tool.importlinter] in pyproject.toml
uv run lint-imports

echo "Checking dependency declarations..."
uv run deptry .

echo "Validating JSON schema files..."

# Function to validate a JSON schema file using Python
validate_schema() {
    local schema_file=$1
    echo "Validating $schema_file..."
    
    # Use Python to validate both JSON syntax and schema validity
    uv run python -c "import json, jsonschema; schema = json.load(open('$schema_file')); jsonschema.Draft7Validator.check_schema(schema)" 2>/dev/null
    
    if [ $? -ne 0 ]; then
        echo "Error: $schema_file is not a valid JSON schema"
        return 1
    fi
    
    return 0
}

# Validate the main agent schema
if ! validate_schema "intentkit/models/agent/schema.json"; then
    exit 1
fi

# Validate all schema.json files in tools subdirectories
echo "Validating schema.json files in tools subdirectories..."
find_exit_code=0

# Find all schema.json files and store them in a temporary file
find intentkit/tools -name "schema.json" > /tmp/schema_files.txt

# Read each line from the temporary file
while IFS= read -r schema_file; do
    if ! validate_schema "$schema_file"; then
        find_exit_code=1
    fi
done < /tmp/schema_files.txt

# Clean up the temporary file
rm -f /tmp/schema_files.txt

if [ $find_exit_code -ne 0 ]; then
    echo "Error: Some schema files are not valid"
    exit 1
fi

echo "All JSON schema files are valid!"
