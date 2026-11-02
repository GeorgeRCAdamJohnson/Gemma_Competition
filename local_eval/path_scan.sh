#!/bin/bash
echo PATH entries and search test:
echo "$PATH" | tr ":" "\n" | while read -r d; do
  if [ -z "$d" ]; then echo "EMPTY"; continue; fi
  if [ ! -e "$d" ]; then echo "MISSING $d"; continue; fi
  if [ ! -d "$d" ]; then echo "NOTDIR $d"; continue; fi
  if [ ! -x "$d" ]; then echo "UNSEARCHABLE $d"; continue; fi
  echo "OK $d"
done
echo --- tools ---
command -v g++ gcc ninja cc
echo --- exec test ---
if nvcc --version >/dev/null 2>&1; then echo nvcc-exec-ok; else echo "nvcc-status=$?"; fi