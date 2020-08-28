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

"""Define settings for the DRAGON plugin."""
import os
import shutil

from voluptuous import Schema, Any

from armi.utils import units
from armi.settings import setting
from armi.operators import settingsValidation
from armi.physics.neutronics import settings as neutronicsSettings
from armi.physics.neutronics import energyGroups
from armi.utils import pathTools

CONF_DRAGON_PATH = "dragonExePath"
CONF_DRAGON_DATA_PATH = "dragonDataPath"
CONF_DRAGON_TEMPLATE_HELPER = "dragonTemplateHelper"

CONF_OPT_DRAGON = "DRAGON"


def defineSettings():
    """Define settings for the DRAGON plugin."""
    settings = [
        setting.Option(CONF_OPT_DRAGON, neutronicsSettings.CONF_XS_KERNEL),
        setting.Setting(
            CONF_DRAGON_PATH,
            default="dragon",
            label="DRAGON exe path",  # label appears on GUI buttons
            description="Path to the DRAGON executable",
        ),
        setting.Setting(
            CONF_DRAGON_DATA_PATH,
            default="draglibendfb7r1SHEM361",
            label="DRAGON nuclear data path",
            description="Path to the DRAGON nuclear data file to use.",
        ),
        setting.Setting(
            CONF_DRAGON_TEMPLATE_HELPER,
            schema=Schema(Any(str, None)),  # Allow None type
            default=None,
            label="DRAGON template helper path",
            description="Path to module responsible for pointing to the DRAGON template",
        ),
    ]
    return settings


def defineValidators(inspector):
    """Define settings validation for the DRAGON plugin."""
    if inspector.cs["xsKernel"] != CONF_OPT_DRAGON:
        # No need to validate DRAGON settings if DRAGON is not being used.
        return []
    queries = [
        settingsValidation.Query(
            lambda: shutil.which(inspector.cs[CONF_DRAGON_PATH]) is None,
            f"The path specified in the `{CONF_DRAGON_PATH}` setting does not exist: "
            f"{inspector.cs[CONF_DRAGON_PATH]}",
            "Please update executable location to the correct location.",
            inspector.NO_ACTION,
        ),
        settingsValidation.Query(
            lambda: not os.path.exists(inspector.cs[CONF_DRAGON_DATA_PATH]),
            "The path specified to the dragon nuclear data file in the "
            f"`{CONF_DRAGON_DATA_PATH}` setting does not exist: "
            f"{inspector.cs[CONF_DRAGON_DATA_PATH]}",
            "Please update nuclear data location to the correct location.",
            inspector.NO_ACTION,
        ),
        settingsValidation.Query(
            lambda: len(energyGroups.getGroupStructure(inspector.cs["groupStructure"]))
            > 33,
            "DRAGON does not run well with more than 33 groups due to calculating "
            "<400 fine groups. This few number of fine groups may not map well onto "
            "more than 33 groups.",
            "Proceed with caution, or choose a group structure with less than 33 groups.",
            inspector.NO_ACTION,
        ),
        settingsValidation.Query(
            lambda: "7r0" in inspector.cs[CONF_DRAGON_DATA_PATH],
            "ENDF/B-VII.0 is selected for DRAGON, but Mo98 is not available in this "
            "library. Your run will likely fail if there is any Mo in your system. ",
            "It is recommended that the nuclear data be switched to ENDF/B-VII.1 or"
            "ENDF/B-VIII.0, or Mo98 be removed from nuclear modeling.",
            inspector.NO_ACTION,
        ),
        settingsValidation.Query(
            lambda: inspector.cs[CONF_DRAGON_TEMPLATE_HELPER] is not None
            and not pathTools.moduleAndAttributeExist(
                inspector.cs[CONF_DRAGON_TEMPLATE_HELPER]
            ),
            "Could not find the DRAGON template helper class described {}. Run will"
            "likely fail during lattice physics calculation.".format(
                inspector.cs[CONF_DRAGON_TEMPLATE_HELPER]
            ),
            "Please update path to point to a module and class that exist.",
            inspector.NO_ACTION,
        ),
    ]
    return queries
