# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
DRAGON Plugin.
"""
from armi import interfaces
from armi import plugins
from armi.physics.neutronics import settings as nSettings
from armi.settings.fwSettings.globalSettings import CONF_VERSIONS

from . import settings
from . import meta


ORDER = interfaces.STACK_ORDER.CROSS_SECTIONS


class DragonPlugin(plugins.ArmiPlugin):
    """Plugin for the DRAGON interface."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Function for exposing interface(s) to other code."""
        from . import dragonInterface

        DragonPlugin.setVersionInSettings(case.cs)

        if (
            cs[nSettings.CONF_XS_KERNEL] == "DRAGON"
            and "Neutron" in cs[nSettings.CONF_GEN_XS]
        ):
            klass = dragonInterface.DragonInterface
            return [interfaces.InterfaceInfo(ORDER, klass, {})]
        return []

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for DRAGON."""
        return settings.defineSettings()

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """Define settings inspections for DRAGON."""
        return settings.defineValidators(inspector)

    @staticmethod
    @plugins.HOOKIMPL
    def defineCaseDependencies(case, suite):
        DragonPlugin.setVersionInSettings(case.cs)

    @staticmethod
    def setVersionInSettings(cs):
        """Helper method to set the version correctly in the Settings file."""
        cs[CONF_VERSIONS]["armi-example-app"] = meta.__version__
