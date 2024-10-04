#!/bin/bash


MYDIR=$(dirname "$0")
python ${MYDIR}/../src/asp_selftest/processors.py $*
