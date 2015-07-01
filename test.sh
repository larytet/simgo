#!/bin/bash

WORK_DIR=`dirname $0`
HELP_STRING="Use command 'exit' to move to the next test"

for SETUP in GTBBTR GTPPTR GTPBTR GTBPTR
do
	echo Run $SETUP
	echo $HELP_STRING
	$WORK_DIR/task1.py pipeline --stages $SETUP
done





