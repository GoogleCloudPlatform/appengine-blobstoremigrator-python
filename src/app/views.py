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
Views for blob-migrator tool.
"""
import os
import json

import cloudstorage
import jinja2
from google.appengine.api import app_identity
from google.appengine.api import modules
from google.appengine.api import users
import webapp2

from app import config
from app import migrator
from app import scrubber
import appengine_config


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
    context['IS_DEVSERVER'] = appengine_config.IS_DEVSERVER
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
      'service_account': (app_identity.get_service_account_name() or
                          '[unknown service account on dev_appserver]'),
      'mapping_kind': config.config.MAPPING_DATASTORE_KIND_NAME,
      'config': config.config,
      'config_keys': config.CONFIGURATION_KEYS_FOR_INDEX,
    }
    return context

  def get(self):
    """GET"""
    context = self._get_base_context()
    context['bucket'] = app_identity.get_default_gcs_bucket_name() or ''
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
    if not errors:
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
    pipeline.start(queue_name=config.config.QUEUE_NAME)

    context['root_pipeline_id'] = pipeline.root_pipeline_id
    self.render_response('started.html', **context)


class DeleteMappingEntitiesView(UserView):
  """Forms to delete the Blobstore->GCS mapping entities from Datastore.

  DO NOT USE THIS AFTER DELETING SOURCE BLOBS!!!
  """

  def _get_base_context(self):
    """Generates a context for both GET and POST."""
    context = {
      'mapping_kind': config.config.MAPPING_DATASTORE_KIND_NAME,
    }
    return context

  def get(self):
    """GET"""
    context = self._get_base_context()
    self.render_response('delete-mappings.html', **context)

  def post(self):
    """POST"""
    context = self._get_base_context()
    confirm = 'confirm' in self.request.POST
    errors = []
    if not confirm:
      errors.append('You must select the checkbox if you want to delete the ' +
                    'Blobstore to Cloud Storage mapping entities.')
    if errors:
      context['errors'] = errors
    else:
      pipeline = scrubber.DeleteBlobstoreToGcsFilenameMappings()
      pipeline.start(queue_name=config.config.QUEUE_NAME)
      context['pipeline_id'] = pipeline.root_pipeline_id
    self.render_response('delete-mappings.html', **context)


class DeleteSourceBlobsView(UserView):
  """Forms to delete the source blobs.

  VERIFY THAT ALL BLOBS CORRECTLY MIGRATED BEFORE USING THIS!!!
  """

  def _get_base_context(self):
    """Generates a context for both GET and POST."""
    context = {
      'mapping_kind': config.config.MAPPING_DATASTORE_KIND_NAME,
    }
    return context

  def get(self):
    """GET"""
    context = self._get_base_context()
    self.render_response('delete-blobs.html', **context)

  def post(self):
    """POST"""
    context = self._get_base_context()
    confirm = 'confirm' in self.request.POST
    errors = []
    if not confirm:
      errors.append('You must select the checkbox if you want to delete the ' +
                    'source blobs.')
    if errors:
      context['errors'] = errors
    else:
      pipeline = scrubber.DeleteBlobstoreBlobs()
      pipeline.start(queue_name=config.config.QUEUE_NAME)
      context['pipeline_id'] = pipeline.root_pipeline_id
    self.render_response('delete-blobs.html', **context)
