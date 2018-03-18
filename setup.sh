#!/usr/bin/env bash

set -o errexit
set -o pipefail

if [[ $1 ]]; then
	PYTHON=$1
else
	PYTHON=$(which python2)
fi

echo "Using python executable: $PYTHON"

app=$(basename $(pwd))

virtualenv=$HOME/virtualenv/$app
rm -rf $virtualenv
mkdir -p $virtualenv
$PYTHON $(which virtualenv) $virtualenv
. $virtualenv/bin/activate
pip install -r requirments.txt