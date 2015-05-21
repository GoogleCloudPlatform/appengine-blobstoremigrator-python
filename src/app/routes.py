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
