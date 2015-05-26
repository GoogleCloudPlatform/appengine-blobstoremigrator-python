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
Routes for blob-migrator tool.
"""
import webapp2

ROUTES = [

  ###
  # Various testing hooks
  #
  # app.yaml only allows login:admin, but these urls provide direct access
  # to blobs and GCS files by admins. Uncomment them only if appropriate.
  ###
  # webapp2.Route('/upload-blob', 'app.testviews.UploadBlob'),
  # webapp2.Route('/upload-blob-handler', 'app.testviews.UploadBlobHandler'),
  # webapp2.Route('/upload-success', 'app.testviews.UploadBlobSuccess'),
  # webapp2.Route('/upload-failure', 'app.testviews.UploadBlobFailure'),
  # webapp2.Route('/serve-gcs-file', 'app.testviews.ServeGcsFile'),
  # webapp2.Route('/serve-gcs-file-via-blob-key', 'app.testviews.ServeGcsFileViaBlobKey'),
  # webapp2.Route('/create-test-blobs', 'app.testviews.CreateTestBlob'),
  # webapp2.Route('/view-blobs', 'app.testviews.ViewBlobs'),

  ###
  # Use this page to actually migrate blobs (you will get to submit a form).
  ###
  webapp2.Route('/', 'app.views.IndexView'),

]
