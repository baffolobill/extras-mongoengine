#from django.contrib.contenttypes.models import ContentType
#from django.db import DEFAULT_DB_ALIAS, router
#from django.db.models import get_apps, get_model, get_models, signals, UnavailableApp
from django.utils.encoding import smart_text
from django.utils import six
from django.utils.six.moves import input

from extras_mongoengine.contrib.contenttypes.models import ContentType
from extras_mongoengine.utils import get_apps, get_documents, get_app_label
from mongoengine import signals
from mongoengine.base import get_document
from mongoengine.errors import NotRegistered


def update_contenttypes(app, created_documents, verbosity=2, db=DEFAULT_DB_ALIAS, **kwargs):
    """
    Creates content types for documents in the given app, removing any document
    entries that no longer have a matching document class.
    """
    try:
        get_document('contenttypes.ContentType')
    except NotRegistered:
        return

    ContentType.objects.clear_cache()
    app_documents = get_documents(app)
    if not app_documents:
        return
    # They all have the same app_label, get the first one.
    app_label = get_app_label(app_documents[0])
    app_documents = dict(
        (document.__name__, document)
        for document in app_documents
    )

    # Get all the content types
    content_types = dict(
        (ct.document, ct)
        for ct in ContentType.objects.filter(app_label=app_label)
    )
    to_remove = [
        ct
        for (document_name, ct) in six.iteritems(content_types)
        if document_name not in app_documents
    ]

    cts = [
        ContentType(
            name=document.__name__,
            app_label=app_label,
            document=document_name,
        )
        for (document_name, document) in six.iteritems(app_documents)
        if document_name not in content_types
    ]
    ContentType.objects.insert(cts)
    if verbosity >= 2:
        for ct in cts:
            print("Adding content type '%s | %s'" % (ct.app_label, ct.document))

    # Confirm that the content type is stale before deletion.
    if to_remove:
        if kwargs.get('interactive', False):
            content_type_display = '\n'.join([
                '    %s | %s' % (ct.app_label, ct.document)
                for ct in to_remove
            ])
            ok_to_delete = input("""The following content types are stale and need to be deleted:

%s

Any objects related to these content types by a foreign key will also
be deleted. Are you sure you want to delete these content types?
If you're unsure, answer 'no'.

    Type 'yes' to continue, or 'no' to cancel: """ % content_type_display)
        else:
            ok_to_delete = False

        if ok_to_delete == 'yes':
            for ct in to_remove:
                if verbosity >= 2:
                    print("Deleting stale content type '%s | %s'" % (ct.app_label, ct.document))
                ct.delete()
        else:
            if verbosity >= 2:
                print("Stale content types remain.")


def update_all_contenttypes(verbosity=2, **kwargs):
    for app in get_apps():
        update_contenttypes(app, None, verbosity, **kwargs)

signals.post_init.connect(update_contenttypes)

if __name__ == "__main__":
    update_all_contenttypes()
