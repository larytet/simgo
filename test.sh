#!/bin/bash

WORK_DIR=`dirname $0`

echo Run GTBBTR
$WORK_DIR/task1.py pipeline --stages GTBBTR

echo Run GTPPTR
$WORK_DIR/task1.py pipeline --stages GTPPTR

echo Run GTPBTR
$WORK_DIR/task1.py pipeline --stages GTPBTR

echo Run GTBPTR
$WORK_DIR/task1.py pipeline --stages GTBPTR



