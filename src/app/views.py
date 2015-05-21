"""
Views for blob-migrator tool.
"""
import os
import sys
import json
import logging
import uuid
import random
import string

from google.appengine.api import users, app_identity, modules, files, images
from google.appengine.ext import blobstore
import webapp2
from google.appengine.ext.webapp import blobstore_handlers
import jinja2
import cloudstorage

from appengine_config import IS_DEVSERVER
from app import migrator
from app.config import config, CONFIGURATION_KEYS_FOR_INDEX


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
      os.path.join(os.path.dirname(__file__), '..', 'templates')
    ),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True,
)


class UserView(webapp2.RequestHandler):
  """A user-facing view."""
  def render_response(self, template_name, **context):
    self.response.headers['Content-Type'] = 'text/html'
    template = JINJA_ENVIRONMENT.get_template(template_name)
    context['user'] = users.get_current_user()
    context['application_id'] = app_identity.get_application_id()
    context['module_id'] = modules.get_current_module_name()
    context['version_id'] = modules.get_current_version_name()
    context['IS_DEVSERVER'] = IS_DEVSERVER
    self.response.write(template.render(**context))


class JsonHandler(webapp2.RequestHandler):
  """A JSON-emitting handler."""
  def emit_json(self, data):
    self.response.headers['Content-Type'] = 'application/json'
    self.response.write(json.dumps(data))


class IndexView(UserView):
  """Main migration tool entry point."""

  def _get_base_context(self):
    """Returns context common to GET and POST."""
    context = {
      'service_account': app_identity.get_service_account_name() or \
                         '[unknown service account on dev_appserver]',
      'mapping_kind': config.MAPPING_DATASTORE_KIND_NAME,
      'config': config,
      'config_keys': CONFIGURATION_KEYS_FOR_INDEX,
    }
    return context

  def get(self):
    """GET"""
    context = self._get_base_context()
    self.render_response('index.html', **context)

  def post(self):
    """
    POST

    'bucket' is required.
    """
    context = self._get_base_context()
    bucket = self.request.POST.get('bucket', '').strip()
    context['bucket'] = bucket

    errors = []
    if not bucket:
      errors.append('Bucket name is required.')

    if bucket:
      try:
        cloudstorage.validate_bucket_name(bucket)
      except ValueError as e:
        bucket = None
        errors.append('Invalid bucket name. %s' % e.message)

    # try to write a small file
    if bucket:
      try:
        migrator.write_test_file(bucket)
      except Exception as e:
        errors.append('Could not write a file to <code>%s</code>. '
                      'Ensure that <code>%s</code> '
                      'has Writer access. Message: <code>%s</code>' % (
                        bucket,
                        context['service_account'],
                        e.message))

    if errors:
      context['errors'] = errors
      self.render_response('index.html', **context)
      return

    pipeline = migrator.MigrateAllBlobsPipeline(bucket)
    pipeline.start()

    context['root_pipeline_id'] = pipeline.root_pipeline_id
    self.render_response('started.html', **context)


class CreateTestBlob(UserView):
  """Creates some test blobs using Files API."""

  SAMPLE_CONTENT_TYPES = [
    ('application/octet-stream', 'dat'),
    ('application/json', 'json'),
    ('text/plain', 'txt'),
    ('text/html', 'html'),
  ]

  def get(self):
    """GET"""
    self.render_response('create.html', number=100, maxsize=100000)

  def post(self):
    """
    POST

    'number' and 'maxsize' are required.
    """
    number = self.request.POST.get('number', '')
    maxsize = self.request.POST.get('maxsize', '')
    context = {
      'number': number,
      'maxsize': maxsize,
    }
    errors = []

    try:
      number = int(number.strip())
    except ValueError:
      errors.append('Number must be an integer.')

    try:
      maxsize = int(maxsize.strip())
    except ValueError:
      errors.append('Max Size must be an integer.')

    if number < 1:
      errors.append('Number must be at least 1.')
    if maxsize < 100:
      errors.append('Max Size must be at least 100 bytes.')
    if maxsize > 10000000:
      errors.append('Max Size must be less than 10000000 bytes.')

    if errors:
      context['errors'] = errors
      self.render_response('create.html', **context)
      return

    for index in range(number):
      content_type, extension = random.choice(self.SAMPLE_CONTENT_TYPES)
      kwargs = {
        'mime_type': content_type
      }
      # put an uploaded filename on some random set of files
      if random.random() < 0.5:
        random_chars = \
          ''.join(random.sample(string.letters + string.digits, 12))
        kwargs['_blobinfo_uploaded_filename'] = \
          'testfile-%s-%s.%s' % (index, random_chars, extension)
      output_filename = files.blobstore.create(**kwargs)
      with files.open(output_filename, 'a') as outfile:
        input_bytes = '1' * (random.randint(100, maxsize))
        outfile.write(input_bytes)
      files.finalize(output_filename)

    context['message'] = \
      '%s blob%s created. ' % (number, number > 1 and 's' or '') + \
      '<a href="/view-blobs">View blobs</a>'
    self.render_response('create.html', **context)


class ViewBlobs(UserView):
  """Views blob infos; may be slow!"""

  def get(self):
    """GET"""
    blobs = blobstore.BlobInfo.all()
    self.render_response('view.html', blobs=blobs)


class UploadBlob(UserView):
  """Use form file upload to write a blob (with a filename)."""

  def get(self):
    upload_url = blobstore.create_upload_url('/upload-blob-handler')
    context = {
      'upload_url': upload_url,
    }
    self.render_response('upload-blob.html', **context)


class UploadBlobHandler(blobstore_handlers.BlobstoreUploadHandler):
  """Redirects after uploading."""

  def post(self):
    """POST"""
    try:
      blob_info = self.get_uploads()[0]
      self.redirect('/upload-success?key=%s' % blob_info.key())
    except Exception:
      self.redirect('/upload-failure')


class UploadBlobSuccess(UserView):
  """Called when blob upload succeeds."""

  def get(self):
    """GET"""
    errors = []
    blob_key = blobstore.BlobKey(self.request.GET['key'].strip())
    blob_info = blobstore.BlobInfo.get(blob_key)
    context = {
      'blob_info': blob_info,
      'errors': errors,
    }
    if not blob_info:
      errors.append('Blob "%s" not found.' % blob_key)
    else:
      if blob_info.content_type in ['image/png', 'image/gif', 'image/jpg']:
        context['serving_url'] = images.get_serving_url(blob_key, size=200)
    self.render_response('upload-success.html', **context)


class UploadBlobFailure(UserView):
  """Called when blob upload failes."""

  def get(self):
    """GET"""
    self.render_response('upload-failure.html')


class ServeGcsFile(webapp2.RequestHandler):
  """Serves a GCS file given the filename."""

  def get(self):
    """
    GET

    'filename' is required.
    """
    filename = self.request.GET['filename'].strip()
    stat = cloudstorage.stat(filename)
    gcs_file = cloudstorage.open(filename)
    self.response.headers['Content-type'] = stat.content_type
    self.response.out.write(gcs_file.read())
    gcs_file.close()


class ServeGcsFileViaBlobKey(blobstore_handlers.BlobstoreDownloadHandler):
  """Serves a GCS file given the filename, but through the BlobKey."""

  def get(self):
    """
    GET

    'filename' is required.
    """
    filename = self.request.GET['filename'].strip()
    blob_key_str = blobstore.create_gs_key('/gs' + filename)
    self.send_blob(blob_key_str)
