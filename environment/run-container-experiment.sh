#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

if (( $# > 0 )); then
    exec "$@"
fi

run_01="results/runs/run-01"
run_02="results/runs/run-02"
publication="results/publication"

for target in "$run_01" "$run_02" "$publication"; do
    if [[ -e "$target" ]]; then
        printf 'Refusing to overwrite existing output: %s\n' "$target" >&2
        printf 'Move the existing results or mount an empty results directory.\n' >&2
        exit 2
    fi
done

metadata_directory="$(mktemp -d)"
doctor_output="${metadata_directory}/toolchain.json"
comparison_output="${metadata_directory}/comparison.json"
packages_output="${metadata_directory}/packages.txt"

python3 -m orchestrator doctor \
    --config environment/toolchain.json | tee "$doctor_output"
pacman -Q clang llvm cmake ninja python make | tee "$packages_output"
python3 -m orchestrator validate --scenarios scenarios

python3 -m orchestrator run \
    --config environment/toolchain.json \
    --scenarios scenarios \
    --output "$run_01"

python3 -m orchestrator run \
    --config environment/toolchain.json \
    --scenarios scenarios \
    --output "$run_02"

python3 -m orchestrator compare \
    --left "$run_01" \
    --right "$run_02" | tee "$comparison_output"

python3 -m orchestrator aggregate \
    --run "$run_01" \
    --output "$publication"

cp "$doctor_output" "$publication/toolchain.json"
cp "$comparison_output" "$publication/comparison.json"
cp "$packages_output" "$publication/packages.txt"

printf '\nExperiment completed.\n'
printf 'First run:  %s\n' "$run_01"
printf 'Second run: %s\n' "$run_02"
printf 'Summary:    %s\n' "$publication"
