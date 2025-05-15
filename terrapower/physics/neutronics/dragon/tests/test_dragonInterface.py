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

"""Test the DRAGON lattice physics writer."""
import os
import unittest

from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT

from terrapower.physics.neutronics.dragon import dragonExecutor, dragonInterface, dragonWriter

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
        cls.writer = dragonWriter.DragonWriterHomogenized([block], options)

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