"""
Manages configuration.

To configure these values, you need to adjust appengine_config.py.

E.g., to control the number of shards, you specify in appengine_config.py:

  blobmigrator_NUM_SHARDS = 128

See appengine_config.py for all the possible configurations.
"""
from google.appengine.api import lib_config


CONFIG_NAMESPACE = "blobmigrator"


class _ConfigDefaults(object):
  """Default configs.

  NUM_SHARDS
    The number of shards that will map over the BlobInfo records.

  ROOT_GCS_FOLDER
    If set, all the migrated files will be placed in this folder within
    the bucket.

  DIRECT_MIGRATION_MAX_SIZE
    Blobs smaller than this size will be directly copied within the
    MapperPipelines. Blobs larger than this size will be copied using
    a secondary MapperPipeline. Editing this value is not recommended.

  MAPPING_DATASTORE_KIND_NAME
    The name of the Datastore kind that will hold the mapping from old
    blob key to new GCS filename and new blob key.
  """

  NUM_SHARDS = 16

  ROOT_GCS_FOLDER = '_blobmigrator_root'

  DIRECT_MIGRATION_MAX_SIZE = 5 * 1024 * 1024

  MAPPING_DATASTORE_KIND_NAME = '_blobmigrator_BlobKeyMapping'


# This is a bit of a hack but does the trick for the UI.
CONFIGURATION_KEYS_FOR_INDEX = [k for k in _ConfigDefaults.__dict__
                                if not k.startswith('_')]


config = lib_config.register(CONFIG_NAMESPACE, _ConfigDefaults.__dict__)
