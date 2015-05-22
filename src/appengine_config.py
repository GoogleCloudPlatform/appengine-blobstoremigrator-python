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
Global configuration for all WSGI apps.
"""
import os
import logging

IS_DEVSERVER = os.environ.get('SERVER_SOFTWARE', '').lower().startswith('devel')

if IS_DEVSERVER:
  logging.getLogger().handlers[0].setLevel(logging.DEBUG)


def webapp_add_wsgi_middleware(app):
  # from google.appengine.ext.appstats import recording
  # app = recording.appstats_wsgi_middleware(app)
  if IS_DEVSERVER:
    logging.debug('\n\n\n')  # space on console between requests
  return app

# NUM_SHARDS
#   The number of shards that will map over the BlobInfo records.
blobmigrator_NUM_SHARDS = 16

# ROOT_GCS_FOLDER
#   If set, all the migrated files will be placed in this folder within
#   the bucket.
blobmigrator_ROOT_GCS_FOLDER = '_blobmigrator_root'

# DIRECT_MIGRATION_MAX_SIZE
#   Blobs smaller than this size will be directly copied within the
#   MapperPipelines. Blobs larger than this size will be copied using
#   a secondary MapperPipeline. Editing this value is not recommended.
blobmigrator_DIRECT_MIGRATION_MAX_SIZE = 5 * 1024 * 1024

# MAPPING_DATASTORE_KIND_NAME
#   The name of the Datastore kind that will hold the mapping from old
#   blob key to new GCS filename and new blob key.
blobmigrator_MAPPING_DATASTORE_KIND_NAME = '_blobmigrator_BlobKeyMapping'

