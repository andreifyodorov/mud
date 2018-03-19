#!/usr/bin/env bash

set -o errexit
set -o pipefail

if [[ $1 ]]; then
	PYTHON=$1
else
	PYTHON=$(which python3.6)
fi

echo "Using python executable: $PYTHON"

app=$(basename $(pwd))

virtualenv=$HOME/virtualenv/$app
rm -rf $virtualenv
mkdir -p $virtualenv
$PYTHON $(which virtualenv) $virtualenv
. $virtualenv/bin/activate

if [[ $(uname -s) == 'Darwin' ]]; then
	pip3.6 install -r requirments_dev.txt
else
	pip3.6 install -r requirments.txt
fi
