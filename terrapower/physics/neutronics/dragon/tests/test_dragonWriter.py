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

"""Unit tests for writers."""

import os
import unittest

from armi.nucDirectory import nuclideBases
from armi.physics.neutronics import energyGroups
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.reactor.flags import Flags
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.settings import caseSettings

from terrapower.physics.neutronics.dragon import dragonExecutor, dragonWriter


class TestWriter(unittest.TestCase):
    def setUp(self):
        block = loadTestBlock()
        self.cs = caseSettings.Settings()
        self.cs[CONF_CROSS_SECTION].setDefaults(self.cs, validBlockTypes=False)
        self.cs["dragonDataPath"] = os.path.join("path", "to", "draglibendfb7r1SHEM361")
        options = dragonExecutor.DragonOptions("test")
        options.fromBlock(block)
        options.fromUserSettings(self.cs)
        self.writer = dragonWriter.DragonWriterHomogenized([block], options)

    def test_templateData(self):
        """Test that the template data structure is properly defined."""
        data = self.writer._buildTemplateData()
        self.assertEqual(data["xsId"], "AA")
        self.assertLess(len(data["nucData"]), dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME + 1)
        self.assertEqual(data["nucDataComment"], self.cs["dragonDataPath"])
        self.assertEqual(data["buckling"], bool(self.writer.options.xsSettings.criticalBuckling))
        self.assertEqual(
            len(data["groupStructure"]),
            len(energyGroups.GROUP_STRUCTURE[self.cs["groupStructure"]]) - 1,
            "DRAGON only includes inner group boundaries so there should be 1 less.",
        )


class TestDragonMixture(unittest.TestCase):
    def setUp(self):
        block = loadTestBlock()
        fuel = block.getChildrenWithFlags(Flags.FUEL)[0]
        fuel.setTemperature(600)
        options = dragonExecutor.DragonOptions("test")
        options.fromBlock(block)
        options.nuclides = ["U235", "U238"]
        self.mix = dragonWriter.DragonMixture(block, options, 0)

    def test_mixture(self):
        block = self.mix.armiObj
        # remove graphite so we don't mix TSL and non-TSL carbon
        graphite = list(block.getChildrenWithFlags(Flags.INNER | Flags.LINER))[0]
        block.remove(graphite)
        self.assertAlmostEqual(self.mix.getTempInK(), 873.15)
        mixItem = self.mix.getMixVector()[0]
        self.assertEqual(mixItem.xsid, "AA")
        self.assertEqual(self.mix.getSelfShieldingFlag(nuclideBases.byName["AM242M"], 0.01), "1")

    def test_getDragLibNucID(self):
        """Test conversion of nuclides to DRAGLIB strings."""
        am241m = nuclideBases.byName["AM242M"]
        self.assertEqual(dragonWriter.getDragLibNucID(am241m, []), "Am242m")
        u235 = nuclideBases.byName["U235"]
        self.assertEqual(dragonWriter.getDragLibNucID(u235, []), "U235")
        na23 = nuclideBases.byName["NA23"]
        self.assertEqual(dragonWriter.getDragLibNucID(na23, []), "Na23")


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
