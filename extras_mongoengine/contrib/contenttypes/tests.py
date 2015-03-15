from __future__ import unicode_literals

from django.test.utils import override_settings
from django.utils.http import urlquote
from django.utils import six
from django.utils.encoding import python_2_unicode_compatible

from mongoengine import Document, fields
from mongoengine.django.tests import MongoTestCase
from extras_mongoengine.contrib.contenttypes.models import ContentType
from extras_mongoengine.contrib.sites.models import Site
from extras_mongoengine.utils import register_documents


class ContentTypesTests(MongoTestCase):

    def setUp(self):
        ContentType.drop_collection()
        ContentType.objects.clear_cache()

    def tearDown(self):
        ContentType.drop_collection()
        ContentType.objects.clear_cache()

    def test_get_for_models_empty_cache(self):
        # Empty cache.
        #with self.assertNumQueries(1):
        cts = ContentType.objects.get_for_documents(ContentType, Site)
        self.assertEqual(cts, {
            ContentType: ContentType.objects.get_for_document(ContentType),
            Site: ContentType.objects.get_for_document(Site),
        })

    def test_get_for_models_partial_cache(self):
        # Partial cache
        ContentType.objects.get_for_document(ContentType)
        #with self.assertNumQueries(1):
        cts = ContentType.objects.get_for_documents(ContentType, Site)

        self.assertEqual(cts, {
            ContentType: ContentType.objects.get_for_document(ContentType),
            Site: ContentType.objects.get_for_document(Site),
        })

    def test_get_for_models_full_cache(self):
        # Full cache
        ContentType.objects.get_for_document(ContentType)
        ContentType.objects.get_for_document(Site)
        #with self.assertNumQueries(0):
        cts = ContentType.objects.get_for_documents(ContentType, Site)
        self.assertEqual(cts, {
            ContentType: ContentType.objects.get_for_document(ContentType),
            Site: ContentType.objects.get_for_document(Site),
        })

    def test_missing_model(self):
        """
        Ensures that displaying content types in admin (or anywhere) doesn't
        break on leftover content type records in the DB for which no model
        is defined anymore.
        """
        ct = ContentType.objects.create(
            name='Old model',
            app_label='contenttypes',
            document='OldModel',
        )
        self.assertEqual(six.text_type(ct), 'Old model')
        self.assertIsNone(ct.document_class())

        # Make sure stale ContentTypes can be fetched like any other object.
        # Before Django 1.6 this caused a NoneType error in the caching mechanism.
        # Instead, just return the ContentType object and let the app detect stale states.
        ct_fetched = ContentType.objects.get_for_id(ct.pk)
        self.assertIsNone(ct_fetched.document_class())
