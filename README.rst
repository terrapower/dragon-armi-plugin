.. image:: https://github.com/terrapower/dragon-armi-plugin/workflows/Dragon%20unit%20tests/badge.svg?branch=master
    :target: https://github.com/terrapower/dragon-armi-plugin/actions?query=workflow%3A%22Dragon%20unit%sotests
    :alt: Unit Tests

.. image:: https://github.com/terrapower/dragon-armi-plugin/workflows/Check%20License%20Lines/badge.svg?branch=master
    :target: https://github.com/terrapower/dragon-armi-plugin/actions?query=workflow%3A%22Check%20License%20Lines
    :alt: Copyright TerraPower

=============
Dragon Plugin
=============

This plugin provides mechanisms for :doc:`ARMI <armi:index>` applications to 
drive École Polytechnique de Montréal's lattice code `DRAGON <https://www.polymtl.ca/merlin/version5.htm>`_.

Full documentation is hosted at https://terrapower.github.io/dragon-plugin/

Prerequisites
-------------
* :doc:`Download and install ARMI <armi:user/user_install>`.
* Download and build/install DRAGON from: https://www.polymtl.ca/merlin/version5.htm

Registering the plugin
----------------------
To activate the DRAGON plugin in your ARMI app, ensure it is in your ``PYTHONPATH`` and
register it in your app with code like:

.. code-block:: python

    from armi.apps import App
    from terrapower.physics.neutronics.dragon import DragonPlugin

    class MyApp(App):
        def __init__(self):
            App.__init__(self)
            self._pm.register(DragonPlugin)


.. list-table:: Quick links
   :widths: 30 70

   * - Source code
     - https://github.com/terrapower/dragon-armi-plugin
   * - Documentation
     - https://terrapower.github.io/dragon-plugin
   * - Bug tracker
     - https://github.com/terrapower/dragon-armi-plugin/issues
   * - Plugin directory
     - https://github.com/terrapower/armi-plugin-directory
   * - Contact
     - armi-devs@terrapower.com
