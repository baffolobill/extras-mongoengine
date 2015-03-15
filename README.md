extras-mongoengine
==================

MongoEngine Extras - Field Types and any other wizardry.


Changelog
=========

03/15/2015
1) Added replacement for the django.contrib.contenttypes;
2) Added replacement for the django.contrib.sites;
3) Added: 'get_apps', 'get_app', 'get_documents', 'get_document', 'register_documents', 'load_app', 'app_cache_ready' - in favor of replace the same staff in django.db.models;


Notes
=====
1. There is no signal in MongoEngine which acts like Django's post_syncdb. So ContentType clean up doesn't work as well as addition of new records (it's all about contenttypes/management.py).

2. I decided to add an extra field `site_id` to Site document instead of replacing original MongoDB ObjectId field. The reason is simple: there is no sequence increasing primary key in Mongo, so that the value should still be entered manually. And why not to use for the purpose different field?

3. AppCache (utils.py) works differently. MongoEngine Document's Meta doesn't have a lot of staff which Django's Model has. Document initialization looks different too. For now I used dirty hacks to make it works. Also it seems that `register_documents` doesn't work. When I ran `contenttypes` tests with a document defined in tests.py, its failed because of `get_document` cannot find this document. So I tried to call `register_documents` in different places and it wasn't solve the problem. Maybe `register_documents` will work fine for a documents defined in "app/models.py". I don't need this feature for now, so this note for the future me.
