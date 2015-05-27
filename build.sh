#!/bin/bash
#
# Copyright 2015 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

dir=`dirname $0`

test () {
  fetch_dependencies
  echo "Using PYTHONPATH=$PYTHONPATH"
  exit_status=0
  python $dir/test_runner.py
}

build() {
  fetch_dependencies
}

fetch_dependencies() {
  if [ ! `which pip` ]
  then
    echo "pip not found. pip is required to install dependencies."
    exit 1;
  fi
  pip install --exists-action=s -q -r $dir/requirements.txt -t $dir/src/lib || exit 1
}

case "$1" in
  test)
    test
    ;;
  build)
    build
    ;;
  *)
    echo $"Usage: $0 {test|build}"
    exit 1
esac
