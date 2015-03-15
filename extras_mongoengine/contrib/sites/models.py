from __future__ import unicode_literals

import string

from django.conf import settings
#from django.db import models
#from django.db.models.signals import pre_save, pre_delete
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible
#from django.core.exceptions import ValidationError

from mongoengine import Document, fields, signals
from mongoengine.queryset import QuerySet
from mongoengine.errors import ValidationError


SITE_CACHE = {}


def _simple_domain_name_validator(value):
    """
    Validates that the given value contains no whitespaces to prevent common
    typos.
    """
    if not value:
        return
    checks = ((s in value) for s in string.whitespace)
    if any(checks):
        raise ValidationError(
            _("The domain name cannot contain any spaces or tabs."),
            code='invalid',
        )


class SiteQuerySet(QuerySet):

    def get_current(self):
        """
        Returns the current ``Site`` based on the SITE_ID in the
        project's settings. The ``Site`` object is cached the first
        time it's retrieved from the database.
        """
        from django.conf import settings
        try:
            sid = settings.SITE_ID
        except AttributeError:
            from django.core.exceptions import ImproperlyConfigured
            raise ImproperlyConfigured("You're using the Django \"sites framework\" without having set the SITE_ID setting. Create a site in your database and set the SITE_ID setting to fix this error.")
        try:
            current_site = SITE_CACHE[sid]
        except KeyError:
            current_site = self.get(site_id=sid)
            SITE_CACHE[sid] = current_site
        return current_site

    def clear_cache(self):
        """Clears the ``Site`` object cache."""
        global SITE_CACHE
        SITE_CACHE = {}


@python_2_unicode_compatible
class Site(Document):
    site_id = fields.IntField(
        verbose_name=_('site id'),
        unique=True)
    domain = fields.StringField(
        verbose_name=_('domain name'),
        max_length=100)
    name = fields.StringField(
        verbose_name=_('display name'),
        max_length=50)

    meta = {
        'indexes': [
            'domain',
            'id',
        ],
        'ordering': ['domain'],
        'queryset_class': SiteQuerySet
    }

    class Meta:
        verbose_name = _('site')
        verbose_name_plural = _('sites')

    def __str__(self):
        return self.domain

    def clean(self):
        super(Site, self).clean()
        _simple_domain_name_validator(self.domain)


@python_2_unicode_compatible
class RequestSite(object):
    """
    A class that shares the primary interface of Site (i.e., it has
    ``domain`` and ``name`` attributes) but gets its data from a Django
    HttpRequest object rather than from a database.

    The save() and delete() methods raise NotImplementedError.
    """
    def __init__(self, request):
        self.domain = self.name = request.get_host()

    def __str__(self):
        return self.domain

    def save(self, force_insert=False, force_update=False):
        raise NotImplementedError('RequestSite cannot be saved.')

    def delete(self):
        raise NotImplementedError('RequestSite cannot be deleted.')


def get_current_site(request):
    """
    Checks if contrib.sites is installed and returns either the current
    ``Site`` object or a ``RequestSite`` object based on the request.
    """
    if 'extras_mongoengine.contrib.sites' in settings.INSTALLED_APPS:
        current_site = Site.objects.get_current()
    else:
        current_site = RequestSite(request)
    return current_site


def clear_site_cache(sender, **kwargs):
    """
    Clears the cache (if primed) each time a site is saved or deleted
    """
    instance = kwargs['document']
    try:
        del SITE_CACHE[instance.site_id]
    except KeyError:
        pass
signals.pre_save.connect(clear_site_cache, sender=Site)
signals.pre_delete.connect(clear_site_cache, sender=Site)
