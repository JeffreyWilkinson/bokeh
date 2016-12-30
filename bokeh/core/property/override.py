'''

'''

class Override(object):
    ''' Override aspects of the Propertyfrom a superclass. '''

    def __init__(self, **kwargs):
        if len(kwargs) == 0:
            raise ValueError("Override() doesn't override anything, needs keyword args")
        self.default_overridden = 'default' in kwargs
        if self.default_overridden:
            self.default = kwargs.pop('default')
        if len(kwargs) > 0:
            raise ValueError("Unknown keyword args to Override: %r" % (kwargs))
