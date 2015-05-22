#!/usr/bin/python
# Copyright 2015 Google Inc. All rights reserved.
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

import os
import sys
import unittest

CUR_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(CUR_DIR, 'src')
TEST_DIR = os.path.join(CUR_DIR, 'test')

def _fix_path():
  """
  Finds the google_appengine directory and fixes Python imports to use it.

  (Mostly) copied from Pipelines API.
  """
  if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)
  all_paths = os.environ.get('PYTHONPATH').split(os.pathsep)
  for path_dir in all_paths:
    dev_appserver_path = os.path.join(path_dir, 'dev_appserver.py')
    if os.path.exists(dev_appserver_path):
      google_appengine = os.path.dirname(os.path.realpath(dev_appserver_path))
      sys.path.append(google_appengine)
      # Use the next import will fix up sys.path even further to bring in
      # any dependent lib directories that the SDK needs.
      dev_appserver = __import__('dev_appserver')
      sys.path.extend(dev_appserver.EXTRA_PATHS)
      return

_fix_path()

def run_tests():
  suite = unittest.TestLoader().discover(TEST_DIR, pattern='*_test.py')
  unittest.TextTestRunner(verbosity=1).run(suite)

if __name__ == '__main__':
  run_tests()
