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
Views for manual testing the blob-migrator tool.
"""
import random
import string

import cloudstorage
from google.appengine.api import files
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import webapp2

from app import views


class CreateTestBlob(views.UserView):
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
        random_chars = (
            ''.join(random.sample(string.letters + string.digits, 12)))
        kwargs['_blobinfo_uploaded_filename'] = (
            'testfile-%s-%s.%s' % (index, random_chars, extension))
      output_filename = files.blobstore.create(**kwargs)
      with files.open(output_filename, 'a') as outfile:
        input_bytes = '1' * (random.randint(100, maxsize))
        outfile.write(input_bytes)
      files.finalize(output_filename)

    context['message'] = (
        '%s blob%s created. ' % (number, number > 1 and 's' or '') +
        '<a href="/view-blobs">View blobs</a>')
    self.render_response('create.html', **context)


class ViewBlobs(views.UserView):
  """Views blob infos; may be slow!"""

  def get(self):
    """GET"""
    blobs = blobstore.BlobInfo.all()
    self.render_response('view.html', blobs=blobs)


class UploadBlob(views.UserView):
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


class UploadBlobSuccess(views.UserView):
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


class UploadBlobFailure(views.UserView):
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
