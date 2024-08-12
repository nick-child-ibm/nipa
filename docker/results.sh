#!/bin/bash

set -euo pipefail

find nipa-run/results -name retcode | xargs grep . | awk 'BEGIN { FS=":" } { print $2 "\t" $1 }'

printf "FAILED: "
find nipa-run/results -name retcode | xargs grep . | awk 'BEGIN { FS=":" } { print $2 "\t" $1 }' | grep -v -e "^0" | wc -l
printf "PASSED: "
find nipa-run/results -name retcode | xargs grep . | awk 'BEGIN { FS=":" } { print $2 "\t" $1 }' | grep -e "^0" | wc -l

