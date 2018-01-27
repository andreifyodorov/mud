#!/usr/bin/env bash

set -o errexit
set -o pipefail

if [[ $(uname -s) != 'Darwin' ]]; then
	echo This script is meant to be run localy
	echo
	exit 1
fi

virtualenv=$HOME/virtualenv/$(basename $(pwd))
if [[ ! -d $virtualenv ]]; then
	mkdir -p $virtualenv
	virtualenv $virtualenv
fi
. $virtualenv/bin/activate
pip install -r requirments.txt

# run ssh tunnel
ssh -N -R 8080:localhost:5000 bakunin.nl &
trap "kill %1" EXIT

# run local server
FLASK_APP=app.py FLASK_DEBUG=1 IS_PLAYGROUND=1 python -m flask run