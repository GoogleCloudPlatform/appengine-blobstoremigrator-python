"""
Pipeline classes to iterate and migrate blobstore blobs to Cloud Storage.
"""
import uuid
import json
import logging

from google.appengine.ext import blobstore
from mapreduce import context
from mapreduce.mapreduce_pipeline import MapperPipeline
from mapreduce.operation import counters
from mapreduce.input_readers import BlobstoreLineInputReader, \
                                    DatastoreInputReader, \
                                    InputReader, \
                                    _get_params
import pipeline
import cloudstorage

from appengine_config import IS_DEVSERVER
from app.models import BlobKeyMapping
from app.config import config

# Controls the size of the chunk that is copied; i.e., this is the size
# of the RAM that will hold the chunk of blob while copying.
BLOB_BUFFER_SIZE = 1024*1024


class BlobstoreDatastoreInputReader(DatastoreInputReader):
  """Override kind lookup method because BlobInfo isn't actually a Model."""

  @classmethod
  def _get_raw_entity_kind(cls, model_classpath):
    """Return hard-coded BlobInfo kind."""
    return blobstore.BLOB_INFO_KIND


class BlobstoreInputReader(InputReader):

  BLOB_KEY_PARAM = 'blob_key'
  START_POSITION_PARAM = 'start_position'
  END_POSITION_PARAM = 'end_position'

  def __init__(self, blob_key, start_position, end_position):
    """Initializes this instance with the given blob key and character range."""
    self.blob_key = blob_key
    self.start_position = start_position
    self.end_position = end_position
    self.blob_reader = blobstore.BlobReader(blob_key,
                                            position=start_position,
                                            buffer_size=BLOB_BUFFER_SIZE)

  def next(self):
    """Returns the next input from this input reader as a key, value pair.

    Returns:
      The next input from this input reader.
    """
    start_position = self.blob_reader.tell()
    if start_position > self.end_position:
      raise StopIteration()
    chunk = self.blob_reader.read(BLOB_BUFFER_SIZE)
    if not chunk:
      raise StopIteration()
    return start_position, chunk

  @classmethod
  def from_json(cls, input_shard_state):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      input_shard_state: The InputReader state as a dict-like object.

    Returns:
      An instance of the InputReader configured using the values of json.
    """
    return cls(input_shard_state[cls.BLOB_KEY_PARAM],
               input_shard_state[cls.START_POSITION_PARAM],
               input_shard_state[cls.END_POSITION_PARAM])

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A json-izable version of the remaining InputReader.
    """
    new_position = self.blob_reader.tell()
    return {
      self.BLOB_KEY_PARAM: self.blob_key,
      self.START_POSITION_PARAM: new_position,
      self.END_POSITION_PARAM: self.end_position,
    }

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of input readers.

    This method creates a list of input readers, each for one shard.
    It attempts to split inputs among readers evenly.

    Args:
      mapper_spec: model.MapperSpec specifies the inputs and additional
        parameters to define the behavior of input readers.

    Returns:
      A list of InputReaders. None or [] when no input data can be found.
    """
    params = _get_params(mapper_spec)
    blob_key = params[cls.BLOB_KEY_PARAM]
    blob_info = blobstore.BlobInfo.get(blobstore.BlobKey(blob_key))
    if not blob_info:
      return None
    return [cls(blob_key, 0, blob_info.size)] # one shard per blob

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Input reader parameters are expected to be passed as "input_reader"
    subdictionary in mapper_spec.params.

    Pre 1.6.4 API mixes input reader parameters with all other parameters. Thus
    to be compatible, input reader check mapper_spec.params as well and
    issue a warning if "input_reader" subdicationary is not present.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Input reader class mismatch")
    params = _get_params(mapper_spec)
    if cls.BLOB_KEY_PARAM not in params:
      raise BadReaderParamsError("Must specify 'blob_key' for mapper input")
    blob_key = params[cls.BLOB_KEY_PARAM]
    blob_info = blobstore.BlobInfo.get(blobstore.BlobKey(blob_key))
    if not blob_info:
      raise BadReaderParamsError("Could not find BlobInfo for key %s" %
                                 blob_key)


def _get_blob_key_str(blob_info_or_key):
  """Gets the BlobKey str from a dynamic input."""
  if isinstance(blob_info_or_key, blobstore.BlobInfo):
    return str(blob_info_or_key.key())
  if isinstance(blob_info_or_key, blobstore.BlobKey):
    return str(blob_info_or_key)
  assert(isinstance(blob_info_or_key, basestring))
  return blob_info_or_key


def migrate_blob(blob_info, _mapper_params=None):
  """Starts a mapper pipeline to migrate single blob to cloud storage object."""

  params = _mapper_params or context.get().mapreduce_spec.mapper.params
  bucket_name = params['bucket_name']

  yield counters.Increment('BlobInfo_considered_for_migration')

  blob_key_str = _get_blob_key_str(blob_info)

  # dev_appserver's stubs store the GCS blobs in the same place as blobstore
  # blobs. We'll skip these so our testing is cleaner.
  if IS_DEVSERVER and blob_key_str.startswith('encoded_gs_file:'):
    yield counters.Increment(
      'BlobInfo_is_really_GCS_file_on_dev_appserver__skipping')
    raise StopIteration()

  # look up the blob_key in the migration table; if already migrated, skip it
  already_mapped = BlobKeyMapping.build_key(blob_key_str).get()
  if already_mapped:
    yield counters.Increment('BlobInfo_previously_migrated')
    raise StopIteration()  # no work to do for this blob

  # if the blob is "small", migrate it in-line
  if blob_info.size <= config.DIRECT_MIGRATION_MAX_SIZE:
    migrate_single_blob_inline(blob_info, bucket_name)
    yield counters.Increment('BlobInfo_migrated_within_mapper')

  # else start a full-scale pipeline to handle the blob migration
  else:
    # start a new pipeline to migrate the blob
    pipeline = MigrateSingleBlobPipeline(blob_key_str,
                                         blob_info.filename,
                                         blob_info.content_type,
                                         bucket_name)
    pipeline.start()
    yield counters.Increment('BlobInfo_migrated_via_secondary_pipeline')

  yield counters.Increment('BlobInfo_migrated')
  raise StopIteration()


def yield_data(data):
  """Simply yields data."""
  start_position, chunk = data
  yield chunk


def build_gcs_filename(blob_info_or_key,
                       filename=None,
                       bucket_name=None,
                       include_bucket=False,
                       include_leading_slash=False):
  """
  Builds a GCS filename.

  If all values are provided, and both include_bucket and include_leading_slash
  are True and ROOT_GCS_FOLDER is CONFIGURED, the resulting GCS filename will
  look like:

    /[bucket_name]/[ROOT_GCS_FOLDER]/[blob_key_str]/[filename]

  Other possible return values (depending on config and inputs) are:

    [ROOT_GCS_FOLDER]/[blob_key_str]
    /[ROOT_GCS_FOLDER]/[blob_key_str]
    [blob_key_string]
    /[blob_key_string]
    [blob_key_string]/[filename]
    /[blob_key_string]/[filename]
    [bucket_name]/[blob_key_string]
    /[bucket_name]/[blob_key_string]
    ...
  """
  blob_key_str = _get_blob_key_str(blob_info_or_key)
  # shred the filename a bit so that the storage broswer has a hope of working
  gcs_filename = '%s/%s/%s/%s/%s' % (blob_key_str[0:8],  # keys have same start
                                     blob_key_str[8:10],
                                     blob_key_str[10:12],
                                     blob_key_str[12:14],
                                     blob_key_str)

  # add the filename to the end, if specified
  if filename:
    gcs_filename += '/' + filename

  # prepend the root folder
  root_folder = config.ROOT_GCS_FOLDER
  if not root_folder:
    root_folder = ''
  root_folder = root_folder.strip('/')  # remove any leading/trailing slash
  if root_folder:
    gcs_filename = root_folder + '/' + gcs_filename

  # prepend the bucket including a leading slash, if specified
  if include_bucket:
    if not bucket_name:
      raise ValueError('bucket_name is required.')
    cloudstorage.validate_bucket_name(bucket_name)
    gcs_filename = '%s/%s' % (bucket_name, gcs_filename)

  if include_leading_slash:
    gcs_filename = '/' + gcs_filename

  return gcs_filename


def build_content_disposition(filename):
  """Builds a content-disposition header"""
  if not filename:
    return ''
  return 'attachment; filename=%s' % filename


class MigrateAllBlobsPipeline(pipeline.Pipeline):
  """Migrate all blobs."""

  def run(self, bucket_name):
    """Run the pipeline"""
    if not bucket_name:
      raise ValueError('bucket_name is required.')
    params = {
      'entity_kind': 'google.appengine.ext.blobstore.blobstore.BlobInfo',
      'bucket_name': bucket_name,
    }
    yield MapperPipeline(
      'iterate_blobs',
      'app.migrator.migrate_blob',
      'app.migrator.BlobstoreDatastoreInputReader',
      params=params,
      shards=config.NUM_SHARDS)


class MigrateSingleBlobPipeline(pipeline.Pipeline):
  """Migrate a single blob into Google Cloud Storage."""


  def run(self, blob_key_str, filename, content_type, bucket_name):
    """Run the pipeline"""

    output_writer_params = {
      'bucket_name': bucket_name,
      'content_type': content_type,
      'naming_format': build_gcs_filename(blob_key_str, filename=filename),
    }
    if filename:
      output_writer_params['content_disposition'] = \
        build_content_disposition(filename)

    params = {
      'blob_key': blob_key_str,
      'blob_keys': blob_key_str,
      'bucket_name': bucket_name,
      'output_writer': output_writer_params,
    }

    output = yield MapperPipeline(
      'copy_blob_to_gcs',
      'app.migrator.yield_data',
      'app.migrator.BlobstoreInputReader',
      output_writer_spec=
        'mapreduce.output_writers.GoogleCloudStorageConsistentOutputWriter',
      params=params,
      shards=1)  # must be 1 because no reducer in MapperPipeline

    yield StoreMappingEntity(blob_key_str, output)


def migrate_single_blob_inline(blob_info, bucket_name):
  """Migrates a single, small blob."""
  options = {}
  if blob_info.filename:
    options['content-disposition'] = \
      build_content_disposition(blob_info.filename)

  gcs_filename = build_gcs_filename(blob_info,
                                    filename=blob_info.filename,
                                    bucket_name=bucket_name,
                                    include_bucket=True,
                                    include_leading_slash=True)

  blob_reader = blobstore.BlobReader(blob_info, buffer_size=BLOB_BUFFER_SIZE)

  gcs_file = cloudstorage.open(gcs_filename,
                               mode='w',
                               content_type=blob_info.content_type,
                               options=options)

  try:
    chunk = blob_reader.read(BLOB_BUFFER_SIZE)
    while chunk:
      gcs_file.write(chunk)
      chunk = blob_reader.read(BLOB_BUFFER_SIZE)
  finally:
    gcs_file.flush()
    gcs_file.close()

  store_mapping_entity(blob_info, gcs_filename)
  return gcs_filename


def write_test_file(bucket_name, delete=True):
  """Writes a 1-byte test file to ensure that bucket is writable."""
  filename = 'test-to-see-if-writable-%s.txt' % uuid.uuid4().hex.lower()
  gcs_filename = '/%s/%s/%s' % (bucket_name, config.ROOT_GCS_FOLDER, filename)
  gcs_file = cloudstorage.open(gcs_filename, mode='w')
  try:
    gcs_file.write('1')
  finally:
    gcs_file.flush()
    gcs_file.close()
  if delete:
    cloudstorage.delete(gcs_filename)

  return gcs_filename


class StoreMappingEntity(pipeline.Pipeline):
  """Store the mapping from old blob key to GCS (and new blob key)."""

  def run(self, old_blob_key_str, output):
    """Run the pipeline"""
    if not output:
      logging.info('No output, means there was no blob to migrate.')
      return
    gcs_filename = output[0]
    store_mapping_entity(old_blob_key_str, gcs_filename)


def store_mapping_entity(old_blob_info_or_key, gcs_filename):
  """Store the mapping in Datastore."""
  if not old_blob_info_or_key:
    raise ValueError('old_blob_info_or_key is required.')
  if not gcs_filename:
    raise ValueError('gcs_filename is required.')
  if not gcs_filename.startswith('/'):
    gcs_filename = '/' + gcs_filename
  old_blob_key_str = _get_blob_key_str(old_blob_info_or_key)
  new_blob_key_str = blobstore.create_gs_key('/gs' + gcs_filename)  # correct?
  kwargs = {
    'key': BlobKeyMapping.build_key(old_blob_key_str),
    'gcs_filename': gcs_filename,
    'new_blob_key': new_blob_key_str,
  }
  entity = BlobKeyMapping(**kwargs)
  entity.put()
  logging.info('Migrated blob_key "%s" to "%s" (GCS file "%s").' % (
               old_blob_key_str, new_blob_key_str, gcs_filename))
  return entity
