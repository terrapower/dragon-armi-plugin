"""
Factory for building DRAGON related objects and their subclasses.

This is an attempt at using an Abstract Factory pattern to allow
applications to configure the dragon plugin as they see necessary. 
Choosing which writer subclasses to use has to be done at some level. 
This factory allows an app to configure its choices in a global
instance of this abstract factory. At some later date it may 
make sense for ARMI to provide a common way for plugins
to self-configure. .
"""


class DragonFactory:
    """
    Build objects based on registration.

    Enables easy customization of the chain of objects needed without excessive subclassing
    """

    def __init__(self):
        self._writers = {}
        self._executers = {}
        self._runners = {}
        self._key = None

    def setKey(self, key):
        """Apply a key to this factory to choose classes with."""
        self._key = key

    def copyEntriesToKey(self, newKey):
        """Copy current registrations into a new key."""
        self._writers[newKey] = self._writers[self._key]
        self._executers[newKey] = self._executers[self._key]
        self._runners[newKey] = self._runners[self._key]

    def registerRunner(self, key, cls):
        self._runners[key] = cls

    def registerWriter(self, key, cls):
        self._writers[key] = cls

    def registerExecuter(self, key, cls):
        self._executers[key] = cls

    def makeRunner(self, objsToRun):
        return self._runners[self._key](objsToRun)

    def makeExecuter(self, opts, obj):
        """Return a new Executer instance."""
        return self._executers[self._key](opts, obj)

    def makeWriter(self, objs, options):
        """Return a new writer instance"""
        return self._writers[self._key](objs, options)


dragonFactory = DragonFactory()
