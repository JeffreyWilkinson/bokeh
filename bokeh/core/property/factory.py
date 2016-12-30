'''

'''

class PropertyFactory(object):
    ''' Base class for objects that can generate Property instances.

    '''

    @classmethod
    def autocreate(cls):
        ''' Called by the MetaHasProps metaclass to create a new instance
        of this descriptor when the property is assigned only using the
        type. For example:

        .. code-block:: python

            class Foo(Model):

                bar = String   # no parens used here

        '''
        return cls()

    def make_descriptors(self, base_name):
        ''' Return a list of Property instances.

        '''
        raise NotImplementedError("make_descriptors not implemented")
