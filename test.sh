#!/bin/bash

WORK_DIR=`dirname $0`
$WORK_DIR/task1.py pipeline --stages GTBBTR
$WORK_DIR/task1.py pipeline --stages GTPPTR
$WORK_DIR/task1.py pipeline --stages GTPBTR
$WORK_DIR/task1.py pipeline --stages GTBPTR


