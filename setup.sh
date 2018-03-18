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
pip3.6 install -r requirments.txt