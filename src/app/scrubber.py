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
Pipeline classes to delete Datastore entities and Blobstore entities.
"""

from google.appengine.ext import blobstore
from mapreduce import mapreduce_pipeline
from mapreduce.operation import counters
from mapreduce.operation import db
import pipeline

from app import config
from app import models


def delete_mapping_entity(mapping_entity_key):
  """Deletes the mapping entity.

  Args:
    mapping_entity_key: The key of the mapping entity to delete.

  Yields:
    A MapReduce datastore delete operation.
  """
  yield db.Delete(mapping_entity_key)
  yield counters.Increment('mapping_entities_deleted')


class DeleteBlobstoreToGcsFilenameMappings(pipeline.Pipeline):
  """Launch a MapReduce job to delete the blobstore->GCS mapping entities."""

  def run(self):
    """Deletes the mapping entiies created in Datastore.

    Be extremely careful with this pipeline. This pipeline is provided
    for convenience in case you need to fully run another blob migration,
    e.g., because you migrated to the wrong bucket the first time.

    If you run this pipeline after deleting the source blobs, you have
    no way to map from old blob keys to new GCS files and it may be
    extremely difficult to use the new GCS files.

    Yields:
      A MapperPipeline for the MapReduce job to delete the mapping entities.
    """
    params = {
      'entity_kind': models.BlobKeyMapping._get_kind(),
    }
    yield mapreduce_pipeline.MapperPipeline(
      'delete_mapping_entities',
      'app.scrubber.delete_mapping_entity',
      'mapreduce.input_readers.DatastoreKeyInputReader',
      params=params,
      shards=config.config.NUM_SHARDS)


def delete_blobstore_blob(mapping_entity_key):
  """Deletes the blobstore blob for the mapping_entity_key.

  Args:
    mapping_entity_key: The key of the mapping entity pointing to the blob
      to delete.
  """
  blob_key = blobstore.BlobKey(mapping_entity_key.name())
  blobstore.delete(blob_key)
  yield counters.Increment('blobs_deleted')


class DeleteBlobstoreBlobs(pipeline.Pipeline):
  """Launch a MapReduce job to delete the blobstore blobs."""

  def run(self):
    """Deletes the blobstore blobs.

    Be extremely careful with this pipeline. This pipeline is used
    to delete the blobstore blobs that have been migrated.

    You must ensure that the blobs have been correctly migrated before
    invoking this pipeline.

    THERE IS NO TURNING BACK!

    Yields:
      A MapperPipeline for the MapReduce job to delete the source blobs.
    """
    params = {
      'entity_kind': models.BlobKeyMapping._get_kind(),
    }
    yield mapreduce_pipeline.MapperPipeline(
      'delete_mapping_entities',
      'app.scrubber.delete_blobstore_blob',
      'mapreduce.input_readers.DatastoreKeyInputReader',
      params=params,
      shards=config.config.NUM_SHARDS)
