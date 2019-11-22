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

from terrapower.physics.neutronics.dragon import dragonInterface
from terrapower.physics.neutronics.dragon import dragonWriter
from terrapower.physics.neutronics.dragon import dragonTemplateHelper
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
        cls.writer = dragonWriter.DragonWriter(
            cls.o,
            block,
            cls.cs,
            cls.o.r.blueprints.allNuclidesInProblem,
            cls.xsId,
            1000.0,
        )

    def test_writeInput(self):
        """
        Test that writing an input is successful.

        Notes
        -----
        This does not actually testing the contents.
        Other unit tests will be depended on for that coverage.
        """
        executors = self.dragonInterface._writeInputs()
        self.cs["dragonTemplateHelper"] = "{}{}".format(
            dragonTemplateHelper.__file__, ":DragonTemplateHelper"
        )
        # Second write is for testing when path is defined.
        executors = self.dragonInterface._writeInputs()
        for executor in executors:
            os.remove(executor.inputName)

    def test_templateData(self):
        """
        Test that the template data structure is properly defined.
        """
        data = self.writer._buildBasicTemplateData()

        # These checks are not exact equal for everything, so that when the test reactor
        # changes they shouldn't need to be updated.
        self.assertEqual(data["xsId"], self.xsId)
        self.assertLess(
            len(data["nucData"]), dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME + 1
        )
        self.assertEqual(data["nucDataComment"], self.cs["dragonDataPath"])
        self.assertEqual(data["tempFuelInKelvin"], 1000)
        self.assertEqual(
            sorted(data["tempComponentsInKelvin"]),
            sorted(units.getTk(Tc=c.temperatureInC) for c in self.writer.b),
        )
        self.assertEqual(data["buckling"], bool(self.xsSettings.criticalBuckling))
        self.assertEqual(
            len(data["groupStructure"]),
            len(units.GROUP_STRUCTURE[self.cs["groupStructure"]]) - 1,
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


class TestDragonExecutor(unittest.TestCase):
    """Test the execution setup and tear down for DRAGON"""

    def setUp(self):
        inputPath = os.path.abspath("myInputName.x2m")
        self.executor = dragonExecutor.DragonExecuter(inputPath, "AA")
        self.executor.cs = settings.Settings()
        self.armiRunDir = THIS_DIR

    def test_setupDir(self):
        """
        Test copy of input, nuclear data and executable to execution dir.

        Notes
        -----
        This test makes small dummy files that it moves around; developers are not
        required to have DRAGON installed to run these tests.
        """
        dragonExeAndDataSettings = ["dragonExePath", "dragonDataPath"]

        # test specific setup
        filesToCopy = []
        for fName in dragonExeAndDataSettings + [self.executor.inputName]:
            # make a dummy file
            fullPath = os.path.abspath(fName)
            with open(fullPath, "w") as f:
                f.write("Dummy Data")
            if fName != "dragonExePath":
                filesToCopy.append(fullPath)

        self.executor.cs["dragonDataPath"] = os.path.abspath("dragonDataPath")
        self.executor.cs["dragonExePath"] = shutil.which("dragonExePath")

        # make some files to copy over to execution dir.
        with directoryChangers.TemporaryDirectoryChanger() as _tempDir:
            self.executor._setupDir()
            # All files (including input) should now exist in both locations.
            for copiedFile in filesToCopy:
                self.assertTrue(os.path.isfile(copiedFile))
                # this one will be removed when the temp dir closes.
                self.assertTrue(os.path.isfile(os.path.basename(copiedFile)))
            # temp dir is set up so lets test execution
            self._runCase()

        for copiedFile in filesToCopy + ["dragonExePath"]:
            os.remove(copiedFile)  # don't leave files around after tests complete.

    def _runCase(self):
        """
        Test execution method.

        Notes
        -----
        This will attempt to execute a text file, causing a failure in subprocess.
        This failure is caught and raised as an XSGenerationError. This test confirms
        that the code up to this error successfully executes.
        """
        self.assertTrue(os.path.isfile(self.executor.cs["dragonDataPath"]))
        expectedRename = self.executor.cs["dragonDataPath"][
            -dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME :
        ]
        # execute a dummy exe
        with self.assertRaises(exceptions.XSGenerationError):
            # This will fail because the exe is a file with the text "Dummy Data".
            # The value of this testing is to make sure none of the code before the
            # suprocess causes failure. The only exception allowed is XSGenerationError.
            self.executor._runCase()

        self.assertTrue(
            os.path.isfile(expectedRename),
            "The DRAGON nuclear data file should have been renamed so the file is 8 "
            "characters of less.",
        )

    def test_getOutputFileNames(self):
        """Test that output file names are created correctly."""
        self.assertEqual(
            self.executor._getOutputFileNames(), ("myInputName.x2mout", "ISOTXS000001")
        )

    def test_copyResults(self):
        """Test that results are copied from the execution dir to the ARMI run dir."""
        self.executor.inputName = "myOtherInputName.x2m"
        dragonOutName, isotxsName = self.executor._getOutputFileNames()

        # copy files from execution dir back to armi run dir
        with directoryChangers.TemporaryDirectoryChanger() as _tempDir:
            with open(dragonOutName, "w") as f:
                f.write("Dummy Data")
            # no isotxs so it should raise this error.
            with self.assertRaises(exceptions.XSGenerationError):
                self.executor._copyResults()
            fPath = os.path.join(self.executor.armiRunDir, dragonOutName)
            self.assertTrue(
                os.path.isfile(fPath),
                f"{fPath} file should have been copied over even though run failed.",
            )

            for fName in (dragonOutName, isotxsName):
                with open(fName, "w") as f:
                    f.write("Dummy Data")

            self.executor._copyResults()
            resultFiles = (dragonOutName, "ISOAA")
            for fName in resultFiles:
                fPath = os.path.join(self.executor.armiRunDir, fName)
                self.assertTrue(
                    os.path.isfile(fPath),
                    f"{fPath} was an output that should have been copied over.",
                )

        for fName in resultFiles:
            os.remove(os.path.join(self.executor.armiRunDir, fName))


if __name__ == "__main__":
    # import sys
    # sys.argv = ["", "TestDragonExecutor"]
    unittest.main()
