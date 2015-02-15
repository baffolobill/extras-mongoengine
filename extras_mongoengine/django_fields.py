import os
import datetime

from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db.models.fields.files import FieldFile, ImageFieldFile
from django.utils.encoding import force_str, force_text

from mongoengine.base import BaseField
from mongoengine.python_support import str_types


class FileField(BaseField):

    proxy_class = FieldFile

    def __init__(self, size=None, upload_to='', storage=None, **kwargs):
        self.size = size
        self.storage = storage or default_storage
        self.upload_to = upload_to

        if callable(upload_to):
            self.generate_filename = upload_to

        super(FileField, self).__init__(**kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        file = instance._data.get(self.name)

        # If this value is a string (instance.file = "path/to/file") or None
        # then we simply wrap it with the appropriate attribute class according
        # to the file field. [This is FieldFile for FileFields and
        # ImageFieldFile for ImageFields; it's also conceivable that user
        # subclasses might also want to subclass the attribute class]. This
        # object understands how to convert a path to a file, and also how to
        # handle None.
        if isinstance(file, str_types) or file is None:
            attr = self.proxy_class(instance, self, file)
            instance._data[self.name] = attr

        # Other types of files may be assigned as well, but they need to have
        # the FieldFile interface added to the. Thus, we wrap any other type of
        # File inside a FieldFile (well, the field's attr_class, which is
        # usually FieldFile).
        elif isinstance(file, File) and not isinstance(file, FieldFile):
            file_copy = self.proxy_class(instance, self, file.name)
            file_copy.file = file
            file_copy._committed = False
            instance._data[self.name] = file_copy

        # Finally, because of the (some would say boneheaded) way pickle works,
        # the underlying FieldFile might not actually itself have an associated
        # file. So we need to reset the details of the FieldFile in those cases.
        elif isinstance(file, FieldFile) and not hasattr(file, 'field'):
            file.instance = instance
            file.field = self
            file.storage = self.storage

        # That was fun, wasn't it?
        return instance._data[self.name]

    def __set__(self, instance, value):
        instance._data[key] = value
        instance._mark_as_changed(key)

    def get_directory_name(self):
        return os.path.normpath(force_text(datetime.datetime.now().strftime(force_str(self.upload_to))))

    def get_filename(self, filename):
        return os.path.normpath(self.storage.get_valid_name(os.path.basename(filename)))

    def generate_filename(self, instance, filename):
        return os.path.join(self.get_directory_name(), self.get_filename(filename))

    def to_mongo(self, value):
        if isinstance(value, self.proxy_class):
            return value.name
        return value


class ImageField(FileField):
    proxy_class = ImageFieldFile

    def __init__(self, width_field=None, height_field=None, **kwargs):
        self.width_field, self.height_field = width_field, height_field
        super(ImageField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        previous_file = instance._data.get(self.name)
        super(ImageField, self).__set__(instance, value)

        # To prevent recalculating image dimensions when we are instantiating
        # an object from the database (bug #11084), only update dimensions if
        # the field had a value before this assignment.  Since the default
        # value for FileField subclasses is an instance of field.attr_class,
        # previous_file will only be None when we are called from
        # Model.__init__().  The ImageField.update_dimension_fields method
        # hooked up to the post_init signal handles the Model.__init__() cases.
        # Assignment happening outside of Model.__init__() will trigger the
        # update right here.
        if previous_file is not None:
            self.update_dimension_fields(instance, force=True)

    def update_dimension_fields(self, instance, force=False, *args, **kwargs):
        """
        Updates field's width and height fields, if defined.
        This method is hooked up to model's post_init signal to update
        dimensions after instantiating a model instance.  However, dimensions
        won't be updated if the dimensions fields are already populated.  This
        avoids unnecessary recalculation when loading an object from the
        database.
        Dimensions can be forced to update with force=True, which is how
        ImageFileDescriptor.__set__ calls this method.
        """
        # Nothing to update if the field doesn't have have dimension fields.
        has_dimension_fields = self.width_field or self.height_field
        if not has_dimension_fields:
            return

        # getattr will call the ImageFileDescriptor's __get__ method, which
        # coerces the assigned value into an instance of self.attr_class
        # (ImageFieldFile in this case).
        file = getattr(instance, self.name)

        # Nothing to update if we have no file and not being forced to update.
        if not file and not force:
            return

        dimension_fields_filled = not(
            (self.width_field and not getattr(instance, self.width_field))
            or (self.height_field and not getattr(instance, self.height_field))
        )
        # When both dimension fields have values, we are most likely loading
        # data from the database or updating an image field that already had
        # an image stored.  In the first case, we don't want to update the
        # dimension fields because we are already getting their values from the
        # database.  In the second case, we do want to update the dimensions
        # fields and will skip this return because force will be True since we
        # were called from ImageFileDescriptor.__set__.
        if dimension_fields_filled and not force:
            return

        # file should be an instance of ImageFieldFile or should be None.
        if file:
            width = file.width
            height = file.height
        else:
            # No file, so clear dimensions fields.
            width = None
            height = None

        # Update the width and height fields.
        if self.width_field:
            setattr(instance, self.width_field, width)
        if self.height_field:
            setattr(instance, self.height_field, height)
