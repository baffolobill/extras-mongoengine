# coding: utf-8
from __future__ import unicode_literals
from inspect import isclass

from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from mongoengine import Document
from mongoengine.base import get_document as mongoengine_get_document
from mongoengine.fields import StringField
from mongoengine.queryset import QuerySet
from extras_mongoengine.utils import get_app_label, get_document


class ContentTypeQuerySet(QuerySet):

    # Cache to avoid re-looking up ContentType objects all over the place.
    # This cache is shared by all the get_for_* methods.
    _cache = {}

    # In the case I find out how to get current DB
    db = 'default'

    def get_by_natural_key(self, app_label, document):
        try:
            ct = self.__class__._cache[self.db][(app_label, document)]
        except KeyError:
            ct = self.get(app_label=app_label, document=document)
            self._add_to_cache(self.db, ct)
        return ct

    def _get_opts(self, document):
        return {
            'app_label': get_app_label(document),
            'document_name': document.__name__,
        }

    def _get_from_cache(self, opts):
        key = (opts['app_label'], opts['document_name'])
        return self.__class__._cache[self.db][key]

    def get_for_document(self, document):
        """
        Returns the ContentType object for a given document, creating the
        ContentType if necessary. Lookups are cached so that subsequent lookups
        for the same document don't hit the database.
        """
        if not isclass(document):
            document = document.__class__

        opts = self._get_opts(document)
        try:
            ct = self._get_from_cache(opts)
        except KeyError:
            # Load or create the ContentType entry.
            ct = self.filter(
                app_label=opts['app_label'],
                document=opts['document_name']
            ).modify(upsert=True, new=True, set__app_label=opts['app_label'],
                set__document=opts['document_name'], set__name=opts['document_name'])
            self._add_to_cache(self.db, ct)

        return ct

    def get_for_documents(self, *documents, **kwargs):
        """
        Given *documents, returns a dictionary mapping {document: content_type}.
        """
        # Final results
        results = {}
        # documents that aren't already in the cache
        needed_app_labels = set()
        needed_documents = set()
        needed_opts = set()
        for document in documents:
            opts = self._get_opts(document)
            try:
                ct = self._get_from_cache(opts)
            except KeyError:
                needed_app_labels.add(opts['app_label'])
                needed_documents.add(opts['document_name'])
                needed_opts.add((opts['app_label'], opts['document_name']))
            else:
                results[document] = ct
        if needed_opts:
            cts = self.filter(
                app_label__in=needed_app_labels,
                document__in=needed_documents
            )
            for ct in cts:
                document = ct.document_class()
                opts = self._get_opts(document)
                key = (opts['app_label'], opts['document_name'])
                if key in needed_opts:
                    results[document] = ct
                    needed_opts.remove(key)
                self._add_to_cache(self.db, ct)
        for app_label, document_name in needed_opts:
            # These weren't in the cache, or the DB, create them.
            ct = self.filter(
                app_label=app_label,
                document=document_name
            ).modify(upsert=True, new=True,
                app_label=app_label, document=document_name, name=document_name)

            self._add_to_cache(self.db, ct)
            results[ct.document_class()] = ct
        return results

    def get_for_id(self, object_id):
        """
        Lookup a ContentType by ID. Uses the same shared cache as get_for_document
        (though ContentTypes are obviously not created on-the-fly by get_by_id).
        """
        try:
            ct = self.__class__._cache[self.db][object_id]
        except KeyError:
            # This could raise a DoesNotExist; that's correct behavior and will
            # make sure that only correct ctypes get stored in the cache dict.
            ct = self.get(pk=object_id)
            self._add_to_cache(self.db, ct)
        return ct

    def clear_cache(self):
        """
        Clear out the content-type cache. This needs to happen during database
        flushes to prevent caching of "stale" content type IDs (see
        django.contrib.contenttypes.management.update_contenttypes for where
        this gets called).
        """
        self.__class__._cache.clear()

    def _add_to_cache(self, using, ct):
        """Insert a ContentType into the cache."""
        # Note it's possible for ContentType objects to be stale; document_class() will return None.
        # Hence, there is no reliance on document._meta.app_label here, just using the document fields instead.
        key = (ct.app_label, ct.document)
        self.__class__._cache.setdefault(using, {})[key] = ct
        self.__class__._cache.setdefault(using, {})[ct.id] = ct



@python_2_unicode_compatible
class ContentType(Document):
    name = StringField(max_length=100)
    app_label = StringField(max_length=100)
    document = StringField(max_length=100, verbose_name=_('python document class name'),
                        unique_with='app_label')


    meta = {
        'ordering': ['name'],
        'indexes': [
            'name',
            ('app_label', 'document'),
        ],
        'queryset_class': ContentTypeQuerySet
    }

    class Meta:
        verbose_name = _('content type')
        verbose_name_plural = _('content types')

    def __str__(self):
        # self.name is deprecated in favor of using document's verbose_name, which
        # can be translated. Formal deprecation is delayed until we have DB
        # migration to be able to remove the field from the database along with
        # the attribute.
        #
        # We return self.name only when users have changed its value from the
        # initial verbose_name_raw and might rely on it.
        document = self.document_class()
        if not document:
            return self.name
        else:
            return document.__name__

    def document_class(self):
        "Returns the Python document class for this type of content."
        return get_document(self.app_label, self.document)

    def mongoengine_document_class(self):
        return mongoengine_get_document("{}.{}".format(
            self.app_label, self.document))

    def get_object_for_this_type(self, **kwargs):
        """
        Returns an object of this type for the keyword arguments given.
        Basically, this is a proxy around this object_type's get_object() document
        method. The ObjectNotExist exception, if thrown, will not be caught,
        so code that calls this method should catch it.
        """
        #return self.document_class().objects.using(self.objects.db).get(**kwargs)
        # I didn't find the place where MongoEngine stores reference to current DB,
        # so for now there is no support for multi-db
        return self.document_class().objects.get(**kwargs)

    def get_all_objects_for_this_type(self, **kwargs):
        """
        Returns all objects of this type for the keyword arguments given.
        """
        #return self.document_class().objects.using(self._state.db).filter(**kwargs)
        return self.document_class().objects.filter(**kwargs)

    def natural_key(self):
        return (self.app_label, self.document)
