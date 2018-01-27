#!/usr/bin/env bash

set -o errexit
set -o pipefail

app=$(basename $(pwd))

virtualenv=$HOME/virtualenv/$app
rm -rf $virtualenv
mkdir -p $virtualenv
virtualenv $virtualenv
. $virtualenv/bin/activate
pip install -r requirments.txt
