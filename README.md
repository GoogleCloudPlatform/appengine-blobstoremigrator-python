# Google App Engine Blobstore to Google Cloud Storage Migration Tool

This tool is a drop-in module that allows you to migrate
all of your Blobstore blobs into a Google Cloud Storage (GCS) bucket.
In doing so, the tool will store a Datastore mapping from the existing
blob key to the GCS filename. Additionally, it is possible to create
a blob key for the new GCS file that can be used with other existing
Google App Engine APIs (e.g.,
[Image API](https://cloud.google.com/appengine/docs/python/images/imageclass#Image));
this new blob key is also stored in the Datastore mapping.

**Note:** this library is written in Python, but because it is a stand-alone
module, it can be used on any App Engine application.

## Getting started

This tool will upload to App Engine as a new module named `blob-migrator`.
Unless you happen to already have a module of that name, you can simply
upload the code without impacting your existing application. (If you do
happen to have a module of that name, you can change this tool by editing
`src/app.yaml`; search for "`module: blob-migrator`".)

First build the source (i.e., download the required libraries) using
the following command:

```
  $ ./build.sh build
```

This will populate the `src/lib` folder with the required libraries.

Upload the `src` directory of this repository to your App Engine application
using `appcfg.py`:

```
  $ appcfg.py update src -A [application-id] -V migrator
```

If you are a user of [Cloud SDK](https://cloud.google.com/sdk/),
you can use the following commands in place of the above command:

```
  $ gcloud auth login

  $ gcloud config set project [application-id]

  $ gcloud preview app deploy src/app.yaml --version migrator
```

Once this tool is uploaded, simply hit the home page of the module.
(Don't worry! The migration will not start immediately; you'll
see some instructions first.)

```
  https://migrator.blob-migrator.[application-id].appspot.com
```

Follow the on-screen instructions, but effectively, all you have to do
is enter the name of a GCS bucket that your application has write access
to and click **Start migration**.

Once complete, all your blobs will have been copied to GCS under the
bucket you specified. Further, a set of mappings from old blob key to
GCS filename and new blob key will be found in Datastore under
the kind `_blobmigrator_BlobKeyMapping` (this name can be modified, see
[*Configuration settings*](#configuration-settings) below).

## Catch-up migrations and re-migrations

The migration tool will skip over blobs that have already been migrated,
so it is safe and efficient to run multiple migrations. This is helpful
because the BlobInfo query is eventually consistent, so if your
application is still writing to Blobstore, or you later find some obscure
code that was continuing to write to Blobstore, you can safely re-run
this migration to catch-up blobs.

If you need to re-migrate some of all of the blobs for some reason,
you can simply delete the appropriate entities in the Datastore
kind `_blobmigrator_BlobKeyMapping`. This tool uses those entities as
the signal that a particular blob has been previously migrated.

If you want to re-migrate *all* the blobs and
you have a large number of mapping entities,
you can use the following tool to
remove all the `_blobmigrator_BlobKeyMapping` entities:

```
  https://migrator.blob-migrator.[application-id].appspot.com/delete-mapping-entities
```

**IMPORTANT** Do not use this tool if you have deleted your source
blobs (see [*Deleting migrated blobs*](#deleting-migrated-blobs) below).
If you delete these entities after the blobs have been deleted, then
it will be extremely difficult to use the newly created
Cloud Storage files.

## Configuration settings

See details in `appengine_config.py` for configurations that can be adjusted.
For example, you can set the root directory within the bucker for all the
migrated files on GCS (`ROOT_GCS_FOLDER`) or the name of the kind that stores
the key mappings on Datastore (`MAPPING_DATASTORE_KIND_NAME`).
Of course, if you edit these settings, you will need to re-upload this tool
for the changes to take effect.

## Deleting migrated blobs

You can use the following tool to delete migrated blobs in Blobstore.
Blobs are only deleted if a mapping `_blobmigrator_BlobKeyMapping`
entity for the blob exists in Datastore.

```
  https://migrator.blob-migrator.[application-id].appspot.com/delete-source-blobs
```

**IMPORTANT** This action _permanently_ _deletes_ migrated blobs in Blobstore.
Before using this tool, you must ensure that the blobs have
been migrated correctly to Cloud Storage and all the
`_blobmigrator_BlobKeyMapping` entities have been created correctly.

## Files API

The test code of this tool uses the deprecated Files API to create
test blobs. If you get a notice from Google that your application is
still using the deprecated Files API, please remember that this tool
may be the cause of this.

This tool uses the Files API only for test code; it is not part of the
mainline migration facility.

Once all your blobs have been migrated successfully, you can delete this
module completely from your application; the blob mappings in Datastore
will remain.
