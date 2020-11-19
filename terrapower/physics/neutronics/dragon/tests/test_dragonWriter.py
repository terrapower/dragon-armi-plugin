"""Unit tests for writers"""
import unittest
import os

from armi.reactor.tests.test_blocks import loadTestBlock
from armi.nucDirectory import nuclideBases
from armi.settings import caseSettings
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.reactor.flags import Flags
from armi.physics.neutronics import energyGroups

from terrapower.physics.neutronics.dragon import dragonWriter
from terrapower.physics.neutronics.dragon import dragonExecutor


class TestWriter(unittest.TestCase):
    def setUp(self):
        block = loadTestBlock()
        self.cs = caseSettings.Settings()
        self.cs[CONF_CROSS_SECTION].setDefaults(self.cs)
        self.cs["dragonDataPath"] = os.path.join("path", "to", "draglibendfb7r1SHEM361")
        options = dragonExecutor.DragonOptions("test")
        options.fromBlock(block)
        options.fromUserSettings(self.cs)
        self.writer = dragonWriter.DragonWriterHomogenized([block], options)

    def test_templateData(self):
        """
        Test that the template data structure is properly defined.
        """
        data = self.writer._buildTemplateData()  # pylint: disable=protected-access
        self.assertEqual(data["xsId"], "AA")
        self.assertLess(
            len(data["nucData"]), dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME + 1
        )
        self.assertEqual(data["nucDataComment"], self.cs["dragonDataPath"])
        self.assertEqual(
            data["buckling"], bool(self.writer.options.xsSettings.criticalBuckling)
        )
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
        self.assertEqual(
            self.mix.getSelfShieldingFlag(nuclideBases.byName["AM242M"], 0.01), "1"
        )

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
