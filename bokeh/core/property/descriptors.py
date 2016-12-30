'''

'''
from __future__ import absolute_import

from copy import copy

from six import string_types

from .containers import PropertyValueContainer


class PropertyDescriptor(object):
    ''' A named attribute that can be read and written.

    '''

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "PropertyDescriptor(%s)" % (self.name)

    def __get__(self, obj, owner=None):
        raise NotImplementedError("Implement __get__")

    def __set__(self, obj, value, setter=None):
        raise NotImplementedError("Implement __set__")

    def __delete__(self, obj):
        raise NotImplementedError("Implement __delete__")

    def class_default(self, cls):
        ''' The default as computed for a certain class, ignoring any
        per-instance theming.

        '''
        raise NotImplementedError("Implement class_default()")

    def serializable_value(self, obj):
        '''Gets the value as it should be serialized.

        Sometimes it is desirable for the serialized value to differ from
        the ``__get__`` in order for the ``__get__`` value to appear simpler
        for user or developer convenience.

        '''
        value = self.__get__(obj)
        return self.property.serialize_value(value)

    def set_from_json(self, obj, json, models, setter=None):
        '''Sets from a JSON value.

        '''
        return self._internal_set(obj, json, setter)

    def add_prop_descriptor_to_class(self, class_name, new_class_attrs, names, names_with_refs, container_names, dataspecs):
        from ..properties import DataSpec, ContainerProperty
        name = self.name
        if name in new_class_attrs:
            raise RuntimeError("Two property generators both created %s.%s" % (class_name, name))
        new_class_attrs[name] = self
        names.add(name)

        if self.has_ref:
            names_with_refs.add(name)

        if isinstance(self, BasicPropertyDescriptor):
            if isinstance(self.property, ContainerProperty):
                container_names.add(name)

            if isinstance(self.property, DataSpec):
                dataspecs[name] = self

    @property
    def serialized(self):
        ''' Whether the property should be serialized when serializing an object.

        This would be False for a "virtual" or "convenience" property that duplicates
        information already available in other properties, for example.

        '''
        raise NotImplementedError("Implement serialized()")

    @property
    def readonly(self):
        ''' Whether this property is read-only.

        Read-only properties may only be modified by the client (i.e., by BokehJS
        in the browser).

        '''
        raise NotImplementedError("Implement readonly()")

    @property
    def has_ref(self):
        ''' True if the property can refer to another HasProps instance.'''
        raise NotImplementedError("Implement has_ref()")

    def trigger_if_changed(self, obj, old):
        ''' Send a change event if the property's value is not equal to ``old``. '''
        raise NotImplementedError("Implement trigger_if_changed()")

class BasicPropertyDescriptor(PropertyDescriptor):
    ''' A Propertyassociated with a class attribute name, so
    it can be read and written.

    '''

    def __init__(self, property, name):
        super(BasicPropertyDescriptor, self).__init__(name)
        self.property = property
        self.__doc__ = self.property.__doc__

    def __str__(self):
        return "%s" % self.property

    def class_default(self, cls):
        '''Get the default value for a specific subtype of HasProps,
        which may not be used for an individual instance.'''
        return self.property.themed_default(cls, self.name, None)

    def instance_default(self, obj):
        ''' Get the default value that will be used for a specific instance.'''
        return self.property.themed_default(obj.__class__, self.name, obj.themed_values())

    @property
    def serialized(self):
        ''' Whether the property should be serialized when serializing an object.

        This would be False for a "virtual" or "convenience" property that duplicates
        information already available in other properties, for example.

        '''
        return self.property.serialized

    @property
    def readonly(self):
        ''' Whether this property is read-only.

        Read-only properties may only be modified by the client (i.e., by BokehJS
        in the browser).

        '''
        return self.property.readonly

    def set_from_json(self, obj, json, models=None, setter=None):
        ''' Sets using the result of serializable_value().

        '''
        return super(BasicPropertyDescriptor, self).set_from_json(obj,
                                                        self.property.from_json(json, models),
                                                        models, setter)

    @property
    def has_ref(self):
        return self.property.has_ref

    def _get(self, obj):
        if not hasattr(obj, '_property_values'):
            raise RuntimeError("Cannot get a property value '%s' from a %s instance before HasProps.__init__" %
                               (self.name, obj.__class__.__name__))

        if self.name not in obj._property_values:
            return self._get_default(obj)
        else:
            return obj._property_values[self.name]

    def __get__(self, obj, owner=None):
        if obj is not None:
            return self._get(obj)
        elif owner is not None:
            return self
        else:
            raise ValueError("both 'obj' and 'owner' are None, don't know what to do")

    def _trigger(self, obj, old, value, hint=None, setter=None):
        if hasattr(obj, 'trigger'):
            obj.trigger(self.name, old, value, hint, setter)

    def _get_default(self, obj):
        if self.name in obj._property_values:
            # this shouldn't happen because we should have checked before _get_default()
            raise RuntimeError("Bokeh internal error, does not handle the case of self.name already in _property_values")

        # merely getting a default may force us to put it in
        # _property_values if we need to wrap the container, if
        # the default is a Model that may change out from
        # underneath us, or if the default is generated anew each
        # time by a function.
        default = self.instance_default(obj)
        if not self.property._has_stable_default():
            if isinstance(default, PropertyValueContainer):
                # this is a special-case so we can avoid returning the container
                # as a non-default or application-overridden value, when
                # it has not been modified.
                default._unmodified_default_value = True
                default._register_owner(obj, self)

            obj._property_values[self.name] = default

        return default

    def _real_set(self, obj, old, value, hint=None, setter=None):
        # As of Bokeh 0.11.1, all hinted events modify in place. However this
        # may need refining later if this assumption changes.
        unchanged = self.property.matches(value, old) and (hint is None)
        if unchanged:
            return

        was_set = self.name in obj._property_values

        # "old" is the logical old value, but it may not be
        # the actual current attribute value if our value
        # was mutated behind our back and we got _notify_mutated.
        if was_set:
            old_attr_value = obj._property_values[self.name]
        else:
            old_attr_value = old

        if old_attr_value is not value:
            if isinstance(old_attr_value, PropertyValueContainer):
                old_attr_value._unregister_owner(obj, self)
            if isinstance(value, PropertyValueContainer):
                value._register_owner(obj, self)

            obj._property_values[self.name] = value

        # for notification purposes, "old" should be the logical old
        self._trigger(obj, old, value, hint, setter)

    def __set__(self, obj, value, setter=None):
        if not hasattr(obj, '_property_values'):
            # Initial values should be passed in to __init__, not set directly
            raise RuntimeError("Cannot set a property value '%s' on a %s instance before HasProps.__init__" %
                               (self.name, obj.__class__.__name__))

        if self.property._readonly:
            raise RuntimeError("%s.%s is a readonly property" % (obj.__class__.__name__, self.name))

        self._internal_set(obj, value, setter)

    def _internal_set(self, obj, value, setter=None):
        value = self.property.prepare_value(obj, self.name, value)

        old = self.__get__(obj)
        self._real_set(obj, old, value, setter=setter)

    # called when a container is mutated "behind our back" and
    # we detect it with our collection wrappers. In this case,
    # somewhat weirdly, "old" is a copy and the new "value"
    # should already be set unless we change it due to
    # validation.
    def _notify_mutated(self, obj, old, hint=None):
        value = self.__get__(obj)

        # re-validate because the contents of 'old' have changed,
        # in some cases this could give us a new object for the value
        value = self.property.prepare_value(obj, self.name, value)

        self._real_set(obj, old, value, hint)

    def __delete__(self, obj):
        if self.name in obj._property_values:
            del obj._property_values[self.name]


    def trigger_if_changed(self, obj, old):
        new_value = self.__get__(obj)
        if not self.property.matches(old, new_value):
            self._trigger(obj, old, new_value)


class DataSpecPropertyDescriptor(BasicPropertyDescriptor):
    """ A descriptor for a DataSpec property. """

    def serializable_value(self, obj):
        return self.property.to_serializable(obj, self.name, getattr(obj, self.name))

    def set_from_json(self, obj, json, models=None, setter=None):
        if isinstance(json, dict):
            # we want to try to keep the "format" of the data spec as string, dict, or number,
            # assuming the serialized dict is compatible with that.
            old = getattr(obj, self.name)
            if old is not None:
                try:
                    self.property._type.validate(old)
                    if 'value' in json:
                        json = json['value']
                except ValueError:
                    if isinstance(old, string_types) and 'field' in json:
                        json = json['field']
                # leave it as a dict if 'old' was a dict

        super(DataSpecPropertyDescriptor, self).set_from_json(obj, json, models, setter)

class UnitsSpecPropertyDescriptor(DataSpecPropertyDescriptor):
    ''' A descriptor for a UnitsSpecProperty that sets a matching
    `_units` property as a side effect.

    '''

    def __init__(self, property, name, units_prop):
        super(UnitsSpecPropertyDescriptor, self).__init__(property, name)
        self.units_prop = units_prop

    def _extract_units(self, obj, value):
        if isinstance(value, dict):
            if 'units' in value:
                value = copy(value) # so we can modify it
            units = value.pop("units", None)
            if units:
                self.units_prop.__set__(obj, units)
        return value

    def __set__(self, obj, value, setter=None):
        value = self._extract_units(obj, value)
        super(UnitsSpecPropertyDescriptor, self).__set__(obj, value, setter)

    def set_from_json(self, obj, json, models=None, setter=None):
        json = self._extract_units(obj, json)
        super(UnitsSpecPropertyDescriptor, self).set_from_json(obj, json, models, setter)
