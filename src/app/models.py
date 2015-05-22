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
