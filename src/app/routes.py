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
from webapp2 import Route, SimpleRoute

ROUTES = [

  ###
  # Various testing hooks
  #
  # app.yaml only allows login:admin, but these urls provide direct access
  # to blobs and GCS files by admins. Uncomment them only if appropriate.
  ###
  # Route('/upload-blob', 'app.views.UploadBlob'),
  # Route('/upload-blob-handler', 'app.views.UploadBlobHandler'),
  # Route('/upload-success', 'app.views.UploadBlobSuccess'),
  # Route('/upload-failure', 'app.views.UploadBlobFailure'),
  # Route('/serve-gcs-file', 'app.views.ServeGcsFile'),
  # Route('/serve-gcs-file-via-blob-key', 'app.views.ServeGcsFileViaBlobKey'),
  # Route('/create-test-blobs', 'app.views.CreateTestBlob'),
  # Route('/view-blobs', 'app.views.ViewBlobs'),

  ###
  # Use this page to actually migrate blobs (you will get to submit a form).
  ###
  Route('/', 'app.views.IndexView'),

]
