=============
Dragon Plugin
=============
This code connects `ARMI <https://terrapower.github.io/armi>`_ with the lattice code DRAGON
from École Polytechnique de Montréal.

Prerequisites
-------------
* Download and install ARMI
* Download and build/install DRAGON from: https://www.polymtl.ca/merlin/version5.htm

Registering the plugin
----------------------
To activate the DRAGON plugin in your ARMI app, ensure it is in your ``PYTHONPATH`` and
register it in your app with code like::

    from armi.apps import App
    from terrapower.physics.neutronics.dragon import DragonPlugin

    class MyApp(App):
        def __init__(self):
            App.__init__(self)
            self._pm.register(DragonPlugin)

-------------

.. toctree::
   :maxdepth: 2
   :glob:

   dragon
   *
   
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
