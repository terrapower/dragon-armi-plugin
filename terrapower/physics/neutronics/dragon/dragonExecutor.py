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
Executes DRAGON input files during an ARMI run.
"""
import os
import shutil
import subprocess

from armi import mpiActions
from armi import runLog
from armi.utils import directoryChangers
from armi.utils import outputCache
from armi.localization import exceptions

from . import dragonWriter


class DragonExecuter(mpiActions.MpiAction):
    """
    Responsible for executing DRAGON in parallel.

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

    # DRAGON natively names the ISOTXS file "ISOTXS000001".
    ISOTXS_NAME = "ISOTXS{:06d}"

    def __init__(self, inputPath, xsId):
        mpiActions.MpiAction.__init__(self)

        # The input file will be copied to the current working (temporary) directory,
        # so only the input name is important.
        self.armiRunDir, self.inputName = os.path.split(inputPath)
        self.xsId = xsId

    def invokeHook(self):
        """Perform DRAGON calculation for the current input file."""
        runLog.important(
            "Preparing to run DRAGON with executable: "
            f"{shutil.which(self.cs['dragonExePath'])}, on input: {self.inputName}"
        )

        with directoryChangers.TemporaryDirectoryChanger() as _tempDir:
            self._setupDir()
            self._runCase()
            self._copyResults()

        if self.parallel:
            # Not sending anything back since no parameters were changed.
            self.gather()

    def _setupDir(self):
        """Copy input file, exe, and nuclear data file (DRAGLIB) to run directory."""
        targetsToCopy = (
            os.path.join(self.armiRunDir, self.inputName),
            self.cs["dragonDataPath"],
        )
        for targetPath in targetsToCopy:
            # copy not move since this dir will be deleted.
            shutil.copy(targetPath, os.path.basename(targetPath))

    def _getOutputFileNames(self):
        """
        Return the output file names.

        Notes
        -----
        The author is uncertain what the standard output file extension is for DRAGON.
        The standard extension for input files are `.x2m`,
        so the output files are using `.x2mout`. If there is a more standard extension,
        it is an opportunity for improvement.
        """
        isotxsName = self.ISOTXS_NAME.format(1)  # only expecting 1 ISOTXS at the moment
        # For dragonAA.x2m ---> dragonAA.x2mout
        dragonOutName = f"{self.inputName}out"
        return (dragonOutName, isotxsName)

    def _runCase(self):
        """Execute the DRAGON input."""
        # the Exe, nuclear data, and input are now in current working directory.
        exe = os.path.basename(self.cs["dragonExePath"])

        # DRAGON input files can only reference nuclear data files with less than
        # this many characters.
        dragonData = os.path.basename(self.cs["dragonDataPath"])
        shortName = dragonData[-dragonWriter.N_CHARS_ALLOWED_IN_LIB_NAME :]
        os.rename(dragonData, shortName)
        # Note that nuclear data files is considered an input for cacheCall().
        inputPaths = (self.inputName, shortName)

        outputFileNames = self._getOutputFileNames()
        with open(outputFileNames[0], "w") as outputF, open(self.inputName) as inputF:

            def exectuteDragon():
                try:
                    subprocess.call(
                        exe, stdin=inputF, stdout=outputF, stderr=subprocess.STDOUT
                    )
                except Exception as err:
                    raise exceptions.XSGenerationError() from err

            # This can make execution nearly instantaneous if the input has
            # been executed before.
            outputCache.cacheCall(
                self.cs, exe, inputPaths, outputFileNames, exectuteDragon
            )

    def _copyResults(self):
        """
        Copy the output and ISOTXS back to the ARMI run location.

        Notes
        -----
        The input does not need to be copied since it was copied over from the original
        ARMI run location, and still resides there.
        """
        dragonOutName, isotoxName = self._getOutputFileNames()

        try:
            # Move instead of copy since temp dir is about to be removed
            shutil.move(dragonOutName, os.path.join(self.armiRunDir, dragonOutName))
            shutil.move(isotoxName, os.path.join(self.armiRunDir, f"ISO{self.xsId}"))
        except:
            # outFileName will always exist, but ISOTXS is typically made at the very
            # end of the run. Alternatively, the return code of subprocess could also
            # possible be examined.
            raise exceptions.XSGenerationError(
                f"DRAGON run on {self.inputName} failed."
            )
