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

"""
Utilities and fixtures for tests.
"""
import unittest

from google.appengine.api import lib_config
from google.appengine.ext import testbed

from app import config


class BlobMigratorTestCase(unittest.TestCase):
  """
  Parent class for tests.
  """
  def setUp(self):
    super(BlobMigratorTestCase, self).setUp()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_blobstore_stub()
    self.testbed.init_app_identity_stub()
    self.testbed.init_urlfetch_stub()
    self.testbed.init_files_stub()
    self.testbed.init_taskqueue_stub()

  def tearDown(self):
    super(BlobMigratorTestCase, self).tearDown()
    self.testbed.deactivate()
    # re-build the configuration in case it was changed by the test
    config.config = lib_config.register(config.CONFIG_NAMESPACE,
                                        config._ConfigDefaults.__dict__)
