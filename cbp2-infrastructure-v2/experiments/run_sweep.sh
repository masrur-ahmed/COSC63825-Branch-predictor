#!/bin/sh
# Builds sweep and runs it on every trace; writes results.tsv
# (one row per trace, one column per configuration).
cd "$(dirname "$0")"
g++ -O3 -Wall -o sweep sweep.cc ../src/trace.cc 2>/dev/null || exit 1
out=results.tsv
first=1
for t in $(find ../traces -name '*.trace.*' | sort); do
	name=$(basename "$(dirname "$t")")
	res=$(./sweep "$t")
	if [ $first = 1 ]; then
		printf "trace\t%s\n" "$(echo "$res" | cut -f1 | paste -s -)" > $out
		first=0
	fi
	printf "%s\t%s\n" "$name" "$(echo "$res" | cut -f2 | paste -s -)" >> $out
done
awk -F'\t' 'NR>1 { for (i = 2; i <= NF; i++) s[i] += $i; n++ }
	END { printf "average"; for (i = 2; i <= NF; i++) printf "\t%.3f", s[i]/n; printf "\n" }' $out >> $out
column -t -s "$(printf '\t')" $out
