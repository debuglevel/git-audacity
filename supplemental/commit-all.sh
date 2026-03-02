#!/usr/bin/env bash

set -e
set -u
set -o pipefail

shopt -s nullglob

# Ensure we're inside a git repo
if [ ! -d ".git" ]; then
    echo "Error: Not inside a git repository."
    exit 1
fi

# Measure git dir size BEFORE (bytes)
GIT_BEFORE_BYTES=$(du -sb .git | awk '{print $1}')

# If arguments are provided, use them as the base commit message
if [ "$#" -gt 0 ]; then
    BASE_MSG="$*"
else
    BASE_MSG=""
fi

for file in *.aup3; do
    echo "Processing $file..."

    echo "aup3git explode..."
    python3 aup3git.py explode "$file"
    echo

    echo "git add..."
    git add "${file}.sql.dir"

    echo "Done with $file."
    echo "-------------------------"
    echo
done

echo "git commit..."
if [ -n "$BASE_MSG" ]; then
    git commit -m "$BASE_MSG"
else
    git commit -m "Updated Audacity projects."
fi

# Measure git dir size AFTER (bytes)
GIT_AFTER_BYTES=$(du -sb .git | awk '{print $1}')

# Calculate difference
DIFF_BYTES=$((GIT_AFTER_BYTES - GIT_BEFORE_BYTES))

# Convert to MB (2 decimal places)
GIT_BEFORE_MB=$(awk "BEGIN {printf \"%.2f\", $GIT_BEFORE_BYTES/1024/1024}")
GIT_AFTER_MB=$(awk "BEGIN {printf \"%.2f\", $GIT_AFTER_BYTES/1024/1024}")
DIFF_MB=$(awk "BEGIN {printf \"%.2f\", $DIFF_BYTES/1024/1024}")

echo
echo "======================================"
echo "Git directory size before : ${GIT_BEFORE_MB} MB"
echo "Git directory size after  : ${GIT_AFTER_MB} MB"
echo "Difference                : ${DIFF_MB} MB"
echo "======================================"