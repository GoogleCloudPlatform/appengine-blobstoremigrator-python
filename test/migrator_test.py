"""
Tests for app.migrator
"""
import uuid
import types

from google.appengine.ext import blobstore
from google.appengine.api import files
from google.appengine.api.files.blobstore \
  import get_blob_key as files_get_blob_key
import cloudstorage

from app import migrator
from app.config import config
from app.models import BlobKeyMapping

import mock
from test.base import BlobMigratorTestCase

VALID_BLOB_KEY = '3DBGQDc4oLFrHJMBXaaG3mjVaJ8dEAP0' + \
                 'EC9lijDZgOohYkIWv7EnWpowcavJq7g8'


def _write_gcs_file(data, bucket_name='my-bucket', filename=None):
  """Writes a GCS file; on dev_appserver (unittest) this writes to BlobInfo."""
  gcs_filename = '/%s/%s' % (bucket_name, filename or uuid.uuid4().hex.lower())
  gcs_file = cloudstorage.open(gcs_filename, mode='w')
  gcs_file.write(data)
  gcs_file.flush()
  gcs_file.close()
  return gcs_filename


def _write_blob(data, content_type=None, filename=None):
  """Creates a test blob and returns its BlobInfo."""
  kwargs = {}
  if content_type:
    kwargs['mime_type'] = content_type
  if filename:
    kwargs['_blobinfo_uploaded_filename'] = filename
  output_filename = files.blobstore.create(**kwargs)
  with files.open(output_filename, 'a') as outfile:
    outfile.write(data)
  files.finalize(output_filename)
  blob_key = files_get_blob_key(output_filename)
  blob_info = blobstore.BlobInfo.get(blob_key)
  return blob_info


def _get_blob_info_with_gcs_filename(gcs_filename):
  """Returns a blob_info for using a gcs_filename."""
  query = BlobKeyMapping.query(BlobKeyMapping.gcs_filename==gcs_filename)
  blob_key_str = query.get().new_blob_key
  blob_key = blobstore.BlobKey(blob_key_str)
  blob_info = blobstore.BlobInfo.get(blob_key)
  return blob_info


def _get_blob_with_gcs_filename(gcs_filename):
  """Reads the blob contents using a gcs_filename."""
  blob_info = _get_blob_info_with_gcs_filename(gcs_filename)
  blob_reader = blobstore.BlobReader(blob_info)
  return blob_reader.read()


class GetBlobKeyStrTests(BlobMigratorTestCase):
  """
  Tests for migrator._get_blob_key_str()
  """
  def test_blob_info_returns_key_str(self):
    blob_key = blobstore.BlobKey(VALID_BLOB_KEY)
    blob_info = blobstore.BlobInfo(blob_key)
    key_str = migrator._get_blob_key_str(blob_info)
    self.assertEquals(VALID_BLOB_KEY, key_str)

  def test_blob_key_returns_key_str(self):
    blob_key = blobstore.BlobKey(VALID_BLOB_KEY)
    key_str = migrator._get_blob_key_str(blob_key)
    self.assertEquals(VALID_BLOB_KEY, key_str)

  def test_unicode_returns_same(self):
    in_key_str = u'\u20ac'
    out_key_str = migrator._get_blob_key_str(in_key_str)
    self.assertEquals(in_key_str, out_key_str)

  def test_str_returns_same(self):
    in_key_str = 'foo'
    out_key_str = migrator._get_blob_key_str(in_key_str)
    self.assertEquals(in_key_str, out_key_str)

  def test_other_object_raises_exception(self):
    with self.assertRaises(AssertionError):
      migrator._get_blob_key_str(123)


class MigrateBlobTests(BlobMigratorTestCase):
  """
  Tests for migrator.migrate_blob()
  """
  def setUp(self):
    super(MigrateBlobTests, self).setUp()
    self.bucket_name = 'my-bucket'
    self.mapper_params = {
      'entity_kind': 'google.appengine.ext.blobstore.blobstore.BlobInfo',
      'bucket_name': self.bucket_name,
    }
    self.__old_is_devserver = migrator.IS_DEVSERVER

  def tearDown(self):
    super(MigrateBlobTests, self).tearDown()
    migrator.IS_DEVSERVER = self.__old_is_devserver

  def call_migrate_blob(self, blob_info):
    """Calls the function under test, performing dependency injection."""
    generator = migrator.migrate_blob(blob_info,
                                      _mapper_params=self.mapper_params)
    for yld in generator:
      pass  # drive generator to completion

  def fetch_blobs(self, number, include_gcs_simulations=False):
    """Fetchs blobs up to number."""
    query = blobstore.BlobInfo.all()
    result = []
    for blob_info in query:
      if not include_gcs_simulations and \
        str(blob_info.key()).startswith('encoded_gs_file:'):
        continue
      result.append(blob_info)
      if len(result) == number:
        break
    return result

  def assertNumberOfStoredBlobs(self, expected, include_gcs_simulations=False):
    """Asserts the number of blobs stored."""
    blobs = self.fetch_blobs(expected+1, \
                             include_gcs_simulations=include_gcs_simulations)
    self.assertEquals(expected, len(blobs))

  def assertNumberOfRealBlobs(self, expected):
    self.assertNumberOfStoredBlobs(expected, include_gcs_simulations=False)

  def assertNumberOfGcsSimulationBlobs(self, expected):
    real_blobs = self.fetch_blobs(1000, include_gcs_simulations=False)
    self.assertNumberOfStoredBlobs(expected + len(real_blobs),
                                   include_gcs_simulations=True)

  def test_gcs_simulated_blobs_on_devappserver_do_not_migrate(self):
    migrator.IS_DEVSERVER = True
    gcs_filename = _write_gcs_file('1')
    # assert some pre-conditions which might change over time
    self.assertNumberOfRealBlobs(0)
    self.assertNumberOfGcsSimulationBlobs(1)
    blob_info = self.fetch_blobs(1, include_gcs_simulations=True)[0]
    self.call_migrate_blob(blob_info)
    # assert that the blob_info has not changed (i.e., no new GCS simulations)
    self.assertNumberOfRealBlobs(0)
    self.assertNumberOfGcsSimulationBlobs(1)

  def test_previously_migrated_blobs_do_not_migrate(self):
    blob_info = _write_blob('1')

    # drive a blob through the migration
    self.call_migrate_blob(blob_info)
    self.assertNumberOfRealBlobs(1)
    self.assertNumberOfGcsSimulationBlobs(1)

    # drive it through a second time
    inline_patcher = mock.patch('app.migrator.migrate_single_blob_inline')
    pipeline_patcher = \
      mock.patch('app.migrator.MigrateSingleBlobPipeline.start')
    inline_mock = inline_patcher.start()
    pipeline_mock = pipeline_patcher.start()
    try:
      self.call_migrate_blob(blob_info)
    finally:
      inline_patcher.stop()
      pipeline_mock.stop()

    # ensure that neither of the copying routines were invoked
    self.assertEquals(0, inline_mock.call_count)
    self.assertEquals(0, pipeline_mock.call_count)

    # ensure that no new GCS simulations have appeared
    self.assertNumberOfRealBlobs(1)
    self.assertNumberOfGcsSimulationBlobs(1)

  @mock.patch('app.migrator.MigrateSingleBlobPipeline.start')
  @mock.patch('app.migrator.migrate_single_blob_inline')
  def test_small_blobs_migrate_directly(self,
                                        inline_mock=None, pipeline_mock=None):
    blob_info = _write_blob('1')

    # drive a blob through the migration
    self.call_migrate_blob(blob_info)
    self.assertEquals(1, inline_mock.call_count)
    self.assertEquals(0, pipeline_mock.call_count)

  @mock.patch('app.migrator.MigrateSingleBlobPipeline.start')
  @mock.patch('app.migrator.migrate_single_blob_inline')
  def test_large_blobs_start_pipeline(self,
                                      inline_mock=None, pipeline_mock=None):
    config.DIRECT_MIGRATION_MAX_SIZE = 100
    blob_info = _write_blob('1' * 200)

    # drive a blob through the migration
    self.call_migrate_blob(blob_info)
    self.assertEquals(0, inline_mock.call_count)
    self.assertEquals(1, pipeline_mock.call_count)


class YieldDataTests(BlobMigratorTestCase):
  """
  Tests for migrator.yield_data()
  """
  def test_second_part_of_tuple_yielded(self):
    data = (123, 'my-data')
    generator = migrator.yield_data(data)
    self.assertTrue(isinstance(generator, types.GeneratorType))
    result = next(generator)
    self.assertEquals('my-data', result)

  def test_only_one_item_yielded(self):
    data = (123, 'my-data')
    generator = migrator.yield_data(data)
    next(generator)
    with self.assertRaises(StopIteration):
      next(generator)


class BuildGCSFilenameTests(BlobMigratorTestCase):
  """
  Tests for migrator.build_gcs_filename()
  """
  def setUp(self):
    super(BuildGCSFilenameTests, self).setUp()
    config.ROOT_GCS_FOLDER = 'foo'
    self.blob_part = '%s/%s/%s/%s/%s' % (VALID_BLOB_KEY[0:8],
                                         VALID_BLOB_KEY[8:10],
                                         VALID_BLOB_KEY[10:12],
                                         VALID_BLOB_KEY[12:14],
                                         VALID_BLOB_KEY)

  def test_gcs_filename_starts_with_configured_root(self):
    config.ROOT_GCS_FOLDER = 'foo'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals('foo/%s' % self.blob_part, gcs_filename)

  def test_gcs_filename_can_have_leading_slash_added(self):
    config.ROOT_GCS_FOLDER = 'foo'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY,
                                               include_leading_slash=True)
    self.assertEquals('/foo/%s' % self.blob_part, gcs_filename)

  def test_configured_root_can_be_empty(self):
    config.ROOT_GCS_FOLDER = ''
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals(self.blob_part, gcs_filename)

  def test_configured_root_can_be_None(self):
    config.ROOT_GCS_FOLDER = None
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals(self.blob_part, gcs_filename)

  def test_configured_root_can_start_with_slash(self):
    config.ROOT_GCS_FOLDER = '/foo'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals('foo/%s' % self.blob_part, gcs_filename)

  def test_configured_root_can_end_with_slash(self):
    config.ROOT_GCS_FOLDER = 'foo/'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals('foo/%s' % self.blob_part, gcs_filename)

  def test_configured_root_can_have_multiple_levels(self):
    config.ROOT_GCS_FOLDER = 'foo/bar'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals('foo/bar/%s' % self.blob_part, gcs_filename)

  def test_gcs_filename_is_root_followed_by_blob_key(self):
    blob_key = blobstore.BlobKey(VALID_BLOB_KEY)
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY)
    self.assertEquals('foo/%s' % self.blob_part, gcs_filename)

  def test_gcs_filename_can_have_filename_appended(self):
    filename = 'my-file.txt'
    gcs_filename = \
      migrator.build_gcs_filename(VALID_BLOB_KEY, filename=filename)
    self.assertEquals('foo/%s/%s' % (self.blob_part, filename), gcs_filename)

  def test_bucket_name_added_if_flag_set(self):
    bucket_name = 'my-bucket'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY,
                                               include_bucket=True,
                                               bucket_name=bucket_name)
    self.assertEquals('%s/foo/%s' % (bucket_name, self.blob_part),
                      gcs_filename)

  def test_bucket_name_can_have_leading_slash_added(self):
    bucket_name = 'my-bucket'
    gcs_filename = migrator.build_gcs_filename(VALID_BLOB_KEY,
                                               include_bucket=True,
                                               bucket_name=bucket_name,
                                               include_leading_slash=True)
    self.assertEquals('/%s/foo/%s' % (bucket_name, self.blob_part),
                      gcs_filename)

  def test_bucket_name_is_required_if_flag_set(self):
    with self.assertRaises(ValueError):
      gcs_filename = migrator.build_gcs_filename(self.blob_part,
                                                 include_bucket=True)

  def test_bucket_name_must_be_valid(self):
    with self.assertRaises(ValueError):
      gcs_filename = migrator.build_gcs_filename(self.blob_part,
                                                 include_bucket=True,
                                                 bucket_name='not valid')


class BuildContentDispositionTests(BlobMigratorTestCase):
  """
  Tests for migrator.build_content_disposition()
  """
  def test_empty_string_returned_if_no_filename(self):
    disposition = migrator.build_content_disposition('')
    self.assertEquals('', disposition)
    disposition = migrator.build_content_disposition(None)
    self.assertEquals('', disposition)

  def test_attachment_style_content_disposition_returned_if_filename(self):
    disposition = migrator.build_content_disposition('foo.txt')
    self.assertEquals('attachment; filename=foo.txt', disposition)


class MigrateSingleBlobInlineTests(BlobMigratorTestCase):
  """
  Tests for migrator.migrate_single_blob_inline()
  """
  def test_small_blob_written_to_gcs(self):
    blob_info = _write_blob('1')
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    contents = _get_blob_with_gcs_filename(gcs_filename)
    self.assertEquals('1', contents)

  def test_large_blob_written_to_gcs(self):
    data = '1' * (migrator.BLOB_BUFFER_SIZE + 2)  # force larger than buffer
    blob_info = _write_blob(data)
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    contents = _get_blob_with_gcs_filename(gcs_filename)
    self.assertEquals(data, contents)

  def test_content_disposition_set_if_filename_on_blob(self):
    blob_info = _write_blob('1', filename='my-file.txt')
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    stat = cloudstorage.stat(gcs_filename)
    self.assertEquals('attachment; filename=my-file.txt',
                      stat.metadata['content-disposition'])

  def test_filename_added_to_gcs_filename(self):
    blob_info = _write_blob('1', filename='my-file.txt')
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    self.assertTrue(gcs_filename.endswith('my-file.txt'))

  def test_content_type_added_to_gcs_file(self):
    blob_info = _write_blob('1', content_type='text/plain')
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    stat = cloudstorage.stat(gcs_filename)
    self.assertEquals('text/plain', stat.content_type)

  def test_blob_key_str_in_gcs_filename(self):
    blob_info = _write_blob('1')
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    self.assertTrue(str(blob_info.key()) in gcs_filename)

  def test_blob_key_mapping_written_to_datastore(self):
    blob_info = _write_blob('1')
    gcs_filename = migrator.migrate_single_blob_inline(blob_info, 'my-bucket')
    query = BlobKeyMapping.query(BlobKeyMapping.gcs_filename==gcs_filename)
    entities = query.fetch(2)
    self.assertEquals(1, len(entities))
    entity = entities[0]
    self.assertEquals(gcs_filename, entity.gcs_filename)
    self.assertEquals(str(blob_info.key()), entity.old_blob_key)


class WriteTestFileTests(BlobMigratorTestCase):
  """
  Tests for migrator.write_test_file()
  """
  def test_file_written_to_cloudstorage(self):
    gcs_filename = migrator.write_test_file('my-bucket', delete=False)
    gcs_file = cloudstorage.open(gcs_filename)
    contents = gcs_file.read()
    gcs_file.close()
    self.assertEquals(1, len(contents))

  @mock.patch('cloudstorage.open',
              side_effect=cloudstorage.AuthorizationError())
  def test_raises_AuthorizationError_if_insufficient_perms(self, mock_open):
    with self.assertRaises(cloudstorage.AuthorizationError):
      migrator.write_test_file('unauthed-bucket')


class StoreMappingEntityTests(BlobMigratorTestCase):
  """
  Tests for migrator.store_mapping_entity()
  """
  def test_old_blob_info_or_key_is_required(self):
    with self.assertRaises(ValueError):
      migrator.store_mapping_entity('', '/filename')
    with self.assertRaises(ValueError):
      migrator.store_mapping_entity(None, '/filename')

  def test_gcs_filename_is_required(self):
    with self.assertRaises(ValueError):
      migrator.store_mapping_entity(VALID_BLOB_KEY, '')
    with self.assertRaises(ValueError):
      migrator.store_mapping_entity(VALID_BLOB_KEY, None)

  def test_parameter_can_be_BlobInfo(self):
    blob_key = blobstore.BlobKey(VALID_BLOB_KEY)
    blob_info = blobstore.BlobInfo(blob_key)
    entity = migrator.store_mapping_entity(blob_info, '/bucket/filename')
    self.assertEquals(VALID_BLOB_KEY, entity.old_blob_key)

  def test_parameter_can_be_BlobKey(self):
    blob_key = blobstore.BlobKey(VALID_BLOB_KEY)
    entity = migrator.store_mapping_entity(blob_key, '/bucket/filename')
    self.assertEquals(VALID_BLOB_KEY, entity.old_blob_key)

  def test_parameter_can_be_key_str(self):
    entity = migrator.store_mapping_entity(VALID_BLOB_KEY, '/bucket/filename')
    self.assertEquals(VALID_BLOB_KEY, entity.old_blob_key)

  def test_entity_stored_with_old_blob_str_as_key(self):
    entity = migrator.store_mapping_entity(VALID_BLOB_KEY, '/bucket/filename')
    lookup = entity.key.get()
    self.assertEquals(VALID_BLOB_KEY, lookup.key.id())

  def test_old_blob_key_str_stored(self):
    entity = migrator.store_mapping_entity(VALID_BLOB_KEY, '/bucket/filename')
    lookup = entity.key.get()
    self.assertEquals(VALID_BLOB_KEY, lookup.old_blob_key)

  def test_gcs_filename_stored(self):
    entity = migrator.store_mapping_entity(VALID_BLOB_KEY, '/bucket/filename')
    lookup = entity.key.get()
    self.assertEquals('/bucket/filename', lookup.gcs_filename)

  def test_gcs_filename_can_be_missing_leading_slash(self):
    entity = migrator.store_mapping_entity(VALID_BLOB_KEY, 'bucket/filename')
    lookup = entity.key.get()
    self.assertEquals('/bucket/filename', lookup.gcs_filename)

  def test_new_blob_key_str_stored(self):
    entity = migrator.store_mapping_entity(VALID_BLOB_KEY, '/bucket/filename')
    lookup = entity.key.get()
    expected_new_blob_key_str = blobstore.create_gs_key('/gs/bucket/filename')
    self.assertEquals(expected_new_blob_key_str, lookup.new_blob_key)
