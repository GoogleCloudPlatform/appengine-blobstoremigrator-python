"""
Utilities and fixtures for tests.
"""
import copy
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
