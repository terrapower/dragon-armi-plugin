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

# pylint: disable=protected-access
"""Test the DRAGON lattice physics writer."""
import os
import shutil
import unittest

from armi import settings
from armi.tests import TEST_ROOT
from armi.reactor.tests import test_reactors
from armi.reactor.flags import Flags
from armi.nucDirectory import nuclideBases
from armi.utils import directoryChangers
from armi.utils import units
from armi.physics.neutronics.const import CONF_CROSS_SECTION

from armi.localization import exceptions
from armi.physics.neutronics import energyGroups

from terrapower.physics.neutronics.dragon import dragonInterface
from terrapower.physics.neutronics.dragon import dragonWriter
from terrapower.physics.neutronics.dragon import dragonExecutor

THIS_DIR = os.path.dirname(__file__)


class TestDragonInterface(unittest.TestCase):
    """Test the DRAGON interface."""

    @classmethod
    def setUpClass(cls):
        cls.o, cls.reactor = test_reactors.loadTestReactor(TEST_ROOT)
        cls.cs = cls.o.cs
        xsgm = cls.o.getInterface("xsGroups")
        xsgm.interactBOL()
        xsgm.interactBOC()
        cls.block = cls.reactor.core.getFirstBlock(Flags.FUEL)
        cls.dragonInterface = dragonInterface.DragonInterface(cs=cls.cs, r=cls.reactor)

        # dummy path
        cls.cs["dragonDataPath"] = os.path.join("path", "to", "draglibendfb7r1SHEM361")
        cls.xsId = "AA"
        cls.xsSettings = cls.cs[CONF_CROSS_SECTION][cls.xsId]
        xsGroupManager = cls.dragonInterface.getInterface("xsGroups")
        block = xsGroupManager.representativeBlocks[cls.xsId]
        options = dragonExecutor.DragonOptions("test")
        options.fromReactor(cls.reactor)
        options.fromBlock(block)
        options.fromUserSettings(cls.cs)
        cls.writer = dragonWriter.DragonWriter(block, options)

    def test_writeInput(self):
        """
        Test that writing an input is successful.

        Notes
        -----
        This does not actually testing the contents.
        Other unit tests will be depended on for that coverage.
        """
        self.writer.write()
        os.remove(self.writer.options.inputFile)

    def test_templateData(self):
        """
        Test that the template data structure is properly defined.
        """
        data = self.writer._buildTemplateData()

        # These checks are not exact equal for everything, so that when the test reactor
        # changes they shouldn't need to be updated.
        self.assertEqual(data["xsId"], self.xsId)
        self.assertLess(
            len(data["nucData"]), dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME + 1
        )
        self.assertEqual(data["nucDataComment"], self.cs["dragonDataPath"])
        self.assertAlmostEqual(data["tempFuelInKelvin"], 873.15)
        self.assertEqual(
            sorted(data["tempComponentsInKelvin"]),
            sorted(units.getTk(Tc=c.temperatureInC) for c in self.writer.b),
        )
        self.assertEqual(data["buckling"], bool(self.xsSettings.criticalBuckling))
        self.assertEqual(
            len(data["groupStructure"]),
            len(energyGroups.getGroupStructure(self.cs["groupStructure"])) - 1,
            "DRAGON only includes inner group boundaries so there should be 1 less.",
        )
        self.assertEqual(len(data["components"]), len(self.writer.b))
        self.assertEqual(data["block"], self.writer.b)

        blockNDenseCard = data["blockNDensCard"]

        nucId, dragonId, nDens, selfShieldingFilterData = blockNDenseCard[0]
        self.assertEqual(nucId[-2:], self.xsId)
        self.assertIsInstance(dragonId, str)
        self.assertIsInstance(nDens, float)
        self.assertEqual(
            selfShieldingFilterData["heavyMetal"],
            True,
            "Blocks used to generate cross sections are expected to have heavy metal."
            "It seems the DRAGON interface is not detecting it.",
        )
        for key in ("mixtureMassDensity", "atomFrac"):
            self.assertIsInstance(selfShieldingFilterData[key], float)

    def test_getDragLibNucID(self):
        """Test conversion of nuclides to DRAGLIB strings."""
        am241m = nuclideBases.byName["AM242M"]
        self.assertEqual(self.writer.getDragLibNucID(am241m), "Am242m")
        u235 = nuclideBases.byName["U235"]
        self.assertEqual(self.writer.getDragLibNucID(u235), "U235")
        na23 = nuclideBases.byName["NA23"]
        self.assertEqual(self.writer.getDragLibNucID(na23), "Na23")


if __name__ == "__main__":
    # import sys
    # sys.argv = ["", "TestDragonExecutor"]
    unittest.main()
