#!/usr/bin/env bash

CWD="test/case05"

echo -e "\n======================================================================"
echo -e "==                        TEST CASE 5                               =="
echo -e "======================================================================\n"

./escape.py --debug --test --quit --log ${CWD}/escape.log --config ${CWD}/test.config --service ${CWD}/request.nffg