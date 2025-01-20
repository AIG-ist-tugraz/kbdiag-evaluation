#!/bin/bash

#
# KBDiag
#
# Copyright (c) 2025
#
# @author: Viet-Man Le (vietman.le@ist.tugraz.at)
#

#PROJ_DIR=$HOME/WORK/projects/ConDetect/NeSy4ConDetect
#PROJ_DIR=$HOME/Development/GitHub/NeSy4ConDetect
#PYTHONPATH=$PYTHONPATH:$PROJ_DIR
#export PYTHONPATH
#
#echo $HOME
#echo $PROJ_DIR
#echo $PYTHONPATH

python3 eval.py --task=1 --size=all
python3 eval.py --task=all --size=25