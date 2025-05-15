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
Write input and execute DRAGON given an ARMI object.

Currently limited to handling Blocks only.

This module makes no assumptions about where the block comes from or when the
execution is to be performed.

Scheduling and choosing happens in
:py:mod:`terrapower.physics.neutronics/dragon.dragonInterface` in default runs, or
in other apps.
"""

import os
import shutil
import subprocess

from armi import runLog
from armi.utils import directoryChangers
from armi.utils import outputCache
from armi.reactor import blocks
from armi.settings import caseSettings
from armi.physics import executers
from armi.physics import neutronics

from . import dragonWriter
from . import settings

# DRAGON natively names the ISOTXS file "ISOTXS000001".
ISOTXS_NAME = "ISOTXS{:06d}"


class DragonOptions(executers.ExecutionOptions):
    """Data structure needed to perform a DRAGON execution."""

    def __init__(self, label=None):
        executers.ExecutionOptions.__init__(self, label)
        self.cacheDir = None
        self.nuclides = []
        self.templatePath = None
        self.libDataFile = None
        self.libDataFileShort = None
        self.xsID = None
        self.groupStructure = None

        self.xsSettings = None
        self.inputFile = f"{label}.x2m"
        # outputs
        # For dragonAA.x2m ---> dragonAA.x2mout
        self.outputFile = f"{self.inputFile}out"
        # only expecting 1 ISOTXS at the moment
        self.outputIsotxsName = ISOTXS_NAME.format(1)

    def fromUserSettings(self, cs: caseSettings.Settings):
        """Load settings from a case settings object"""
        self.executablePath = shutil.which(cs[settings.CONF_DRAGON_PATH])
        self.setRunDirFromCaseTitle(cs.caseTitle)
        self.libDataFile = cs[settings.CONF_DRAGON_DATA_PATH]
        _dataPath, dataName = os.path.split(self.libDataFile)
        # DRAGON input files can only reference nuclear data files with less
        # than this many characters. We take the last x chars rather than the
        # first since the library names usually have meaningful info at the end
        # like draglibendfb7r1SHEM31Plugin 'dense-analysis/ale'5
        self.libDataFileShort = dataName[-dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME :]
        self.cacheDir = cs["outputCacheLocation"]
        self.groupStructure = cs["groupStructure"]

        if self.xsID is None:
            raise ValueError("You must run `fromBlock` before `fromUserSettings`")
        self.xsSettings = cs[neutronics.const.CONF_CROSS_SECTION][self.xsID]

        self.templatePath = cs[settings.CONF_DRAGON_TEMPLATE_PATH]

    def fromReactor(self, reactor):
        self.nuclides = reactor.blueprints.allNuclidesInProblem

    def fromBlock(self, block: blocks.Block):
        """Determine specific options from a particular block."""
        self.xsID = block.getMicroSuffix()


class DragonExecuter:
    """
    Execute a DRAGON case given a block.

    Notes
    -----
    DRAGON creates binary files during the run (for example _main001 and _DUMMY).
    These files have the same name regardless of input name or settings so if more than
    one run occurs simultaneously in a directory there will be naming collision issues.
    Therefore, to execute in parallel, the execution occurs in a temporary directory.
    After execution, the output file, and any ISOTXS files are copied to the location
    of the ARMI run (where an input file already resided). The temporary directory is
    also local to the machine, which can help for cluster execution speed.
    Before execution the temporary directory has the input, nuclear data, and executable
    copied over to it for fast execution.
    """

    def __init__(self, options: DragonOptions, block):
        self.options = options
        self.block = block

    def run(self):
        """Perform DRAGON calculation for the current input file."""
        runLog.important(
            "Preparing to run DRAGON with executable: "
            f"{self.options.executablePath}, on input: {self.options.inputFile}"
        )
        self.writeInput()

        inputs, outputs = self._collectIONames()

        with directoryChangers.ForcedCreationDirectoryChanger(
            self.options.runDir,
            filesToMove=inputs,
            filesToRetrieve=outputs,
        ):
            self._execute()

    def _collectIONames(self):
        inputs = (
            self.options.inputFile,
            (self.options.libDataFile, self.options.libDataFileShort),
        )
        outputs = (
            self.options.outputFile,
            # rename isotxs on way back to the shared directory
            (self.options.outputIsotxsName, f"ISO{self.options.xsID}"),
            "*.ps",
        )
        return inputs, outputs

    def writeInput(self):
        """Write the input file."""
        inputWriter = dragonFactory.makeWriter([self.block], self.options)
        inputWriter.write()

    def _execute(self):
        """
        Execute the DRAGON input.

        The nuclear data and input are now in current working directory.

        Notes
        -----
        This makes use of an output caching utility, which can make execution
        nearly instantaneously if the input has been executed before.
        """
        runLog.extra(
            f"Executing {self.options.executablePath}\n"
            f"\tInput: {self.options.inputFile}\n"
            f"\tOutput: {self.options.outputFile}\n"
            f"\tWorking dir: {self.options.runDir}"
        )

        # Note that nuclear data files is considered an input for cacheCall().
        inputPaths = (self.options.inputFile, self.options.libDataFileShort)
        outputPaths = (self.options.outputFile, self.options.outputIsotxsName)

        def executeDragon():
            """Helper function to work with output caching"""
            with open(self.options.outputFile, "w") as outputF, open(self.options.inputFile) as inputF:
                try:
                    subprocess.call(
                        self.options.executablePath,
                        stdin=inputF,
                        stdout=outputF,
                        stderr=subprocess.STDOUT,
                    )
                except Exception as err:
                    raise err

        outputCache.cacheCall(
            self.options.cacheDir,
            self.options.executablePath,
            inputPaths,
            outputPaths,
            executeDragon,
        )


from .dragonFactory import dragonFactory
