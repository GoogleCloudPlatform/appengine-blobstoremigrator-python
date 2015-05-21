"""
Tests for app.models
"""
from app.models import BlobKeyMapping
from app.config import config

from test.base import BlobMigratorTestCase

class BlobKeyMappingTests(BlobMigratorTestCase):
  """
  Tests for BlobKeyMapping
  """
  def test_get_kind_uses_configuration(self):
    config.MAPPING_DATASTORE_KIND_NAME = 'foo'
    kind = BlobKeyMapping._get_kind()
    self.assertEquals('foo', kind)

  def test_build_key_uses_correct_kind(self):
    key = BlobKeyMapping.build_key('abc123')
    self.assertEquals(config.MAPPING_DATASTORE_KIND_NAME, key.kind())

  def test_build_key_uses_provided_id(self):
    key = BlobKeyMapping.build_key('abc123')
    self.assertEquals('abc123', key.id())

  def test_build_key_id_is_required(self):
    with self.assertRaises(ValueError):
      BlobKeyMapping.build_key('')
    with self.assertRaises(ValueError):
      BlobKeyMapping.build_key(None)
