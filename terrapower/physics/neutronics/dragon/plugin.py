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
DRAGON Plugin
"""
from armi import plugins
from armi import interfaces

from . import dragonInterface
from . import settings

ORDER = interfaces.STACK_ORDER.CROSS_SECTIONS


class DragonPlugin(plugins.ArmiPlugin):
    """Plugin for the DRAGON interface."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Function for exposing interface(s) to other code"""
        if cs["xsKernel"] == "DRAGON":
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
