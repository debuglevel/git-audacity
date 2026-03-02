#!/usr/bin/env bash

set -e
set -u
set -o pipefail

shopt -s nullglob

for dir in *.aup3.sql.dir; do
    # Remove the .sql.dir suffix
    project="${dir%.sql.dir}"

    echo "Restoring $project..."

    echo "aup3git implode..."
    python3 aup3git.py implode "$project"
    echo

    echo "Done with $project."
    echo "-------------------------"
    echo
done

echo "All projects restored."
