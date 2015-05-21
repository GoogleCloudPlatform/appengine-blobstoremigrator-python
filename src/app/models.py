"""
Models for blob-migrator tool.
"""
from google.appengine.ext import ndb

from app.config import config


class BlobKeyMapping(ndb.Model):
  """
  Stores a mapping from the old blob key to a new Google Cloud Storage
  filename, as well as a new blob key for the Cloud Storage file that can
  be used in legacy blobstore APIs.
  """
  old_blob_key = ndb.ComputedProperty(lambda self: self.key.id())
  gcs_filename = ndb.StringProperty(required=True)
  new_blob_key = ndb.StringProperty(required=True)

  _use_cache = False
  _use_memcache = False

  @classmethod
  def _get_kind(cls):
    """Returns the kind name."""
    return config.MAPPING_DATASTORE_KIND_NAME

  @classmethod
  def build_key(cls, key_str):
    """Builds a key."""
    if not key_str:
      raise ValueError('key_str is required.')
    return ndb.Key(cls, key_str)
