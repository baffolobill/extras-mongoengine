from __future__ import unicode_literals

from django.conf import settings
from django.http import HttpRequest
from django.test.utils import override_settings

from mongoengine.django.tests import MongoTestCase
from mongoengine.errors import ValidationError
from extras_mongoengine.contrib.sites.models import Site, RequestSite, get_current_site


class SitesFrameworkTests(MongoTestCase):

    def setUp(self):
        Site.drop_collection()
        Site(site_id=settings.SITE_ID, domain="example.com", name="example.com").save()
        #self.old_Site_meta_installed = Site._meta.installed
        #Site._meta.installed = True

    def tearDown(self):
        #Site._meta.installed = self.old_Site_meta_installed
        Site.drop_collection()

    def test_save_another(self):
        # Regression for #17415
        # On some backends the sequence needs reset after save with explicit ID.
        # Test that there is no sequence collisions by saving another site.
        Site(site_id=2, domain="example2.com", name="example2.com").save()

    def test_site_manager(self):
        # Make sure that get_current() does not return a deleted Site object.
        s = Site.objects.get_current()
        self.assertTrue(isinstance(s, Site))
        s.delete()
        self.assertRaises(Site.DoesNotExist, Site.objects.get_current)

    def test_site_cache(self):
        # After updating a Site object (e.g. via the admin), we shouldn't return a
        # bogus value from the SITE_CACHE.
        site = Site.objects.get_current()
        self.assertEqual("example.com", site.name)
        s2 = Site.objects.get(site_id=settings.SITE_ID)
        s2.name = "Example site"
        s2.save()
        site = Site.objects.get_current()
        self.assertEqual("Example site", site.name)

    def test_delete_all_sites_clears_cache(self):
        # When all site objects are deleted the cache should also
        # be cleared and get_current() should raise a DoesNotExist.
        self.assertIsInstance(Site.objects.get_current(), Site)
        Site.objects.all().delete()
        self.assertRaises(Site.DoesNotExist, Site.objects.get_current)

    @override_settings(ALLOWED_HOSTS=['example.com'])
    def test_get_current_site(self):
        # Test that the correct Site object is returned
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "example.com",
            "SERVER_PORT": "80",
        }
        #import pdb; pdb.set_trace()
        site = get_current_site(request)
        self.assertTrue(isinstance(site, Site))
        self.assertEqual(site.site_id, settings.SITE_ID)

        # Test that an exception is raised if the sites framework is installed
        # but there is no matching Site
        site.delete()
        self.assertRaises(Site.DoesNotExist, get_current_site, request)

        # A RequestSite is returned if the sites framework is not installed
        #Site._meta.installed = False
        installed_apps = settings.INSTALLED_APPS
        new_installed_apps = list(installed_apps)
        new_installed_apps.remove('extras_mongoengine.contrib.sites')
        settings.INSTALLED_APPS = new_installed_apps

        site = get_current_site(request)
        self.assertTrue(isinstance(site, RequestSite))
        self.assertEqual(site.name, "example.com")

        settings.INSTALLED_APPS = installed_apps

    def test_domain_name_with_whitespaces(self):
        # Regression for #17320
        # Domain names are not allowed contain whitespace characters
        site = Site(name="test name", domain="test test")
        self.assertRaises(ValidationError, site.clean)
        site.domain = "test\ttest"
        self.assertRaises(ValidationError, site.clean)
        site.domain = "test\ntest"
        self.assertRaises(ValidationError, site.clean)
