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
Triggers DRAGON input writing, execution, and output reading during an ARMI run.
"""

from armi import runLog
from armi import interfaces
from armi.nuclearDataIO import isotxs
from armi.physics import neutronics
from armi.physics.neutronics.latticePhysics import latticePhysicsInterface
from armi.nuclearDataIO import xsLibraries
from armi import mpiActions

from . import dragonExecutor


class DragonInterface(interfaces.Interface):
    """"Schedules activities related to DRAGON during ARMI run."""

    name = "dragon"  # name is required for all interfaces
    function = latticePhysicsInterface.LATTICE_PHYSICS

    def interactBOC(self, cycle=None):
        """Run DRAGON on various representative blocks, producing microscopic cross sections."""
        runLog.info("Running DRAGON to update cross sections.")
        mpiActions.DistributeStateAction.invokeAsMaster(self.o, self.r, self.cs)

        dragonRunner = DragonRunner()
        # Run on any potential worker mpi nodes
        dragonRunner.broadcast()
        # Run on this process as well
        dragonRunner.invoke(self.o, self.r, self.cs)

        self._mergeISOTXS()

    def _mergeISOTXS(self):
        """Merge all the ISOTXS files together so that can be run for global flux."""

        # Create an empty ISOTXS library to be filled in with XS data
        lib = xsLibraries.IsotxsLibrary()

        neutronVelocities = xsLibraries.mergeXSLibrariesInWorkingDirectory(lib)
        latticePhysicsInterface.setBlockNeutronVelocities(self.r, neutronVelocities)

        isotxs.writeBinary(lib, neutronics.ISOTXS)


class DragonRunner(mpiActions.MpiAction):
    """
    Run a set of DRAGON runs, possibly in parallel.

    MpiActions have access to the operator and the reactor and can therefore
    reach in as appropriate to select which blocks to execute on in a 
    analysis-specific way.

    Builds DragonExecuters to run each individual case.
    """

    def invokeHook(self):
        """Perform DRAGON calculation for the blocks assigned to this process."""
        for b in self.mpiIter(selectBlocksToRun(self.o)):
            executer = self._buildExecuterForBlock(b)
            executer.run()

        if self.parallel:
            self.gather()
            self.r.syncMpiState()

    def _buildExecuterForBlock(self, b):
        """Build options and executers for a block."""
        opts = dragonExecutor.DragonOptions(
            label=f"dragon-{b.getName()}-{self.r.p.cycle}-{self.r.p.timeNode}"
        )

        opts.fromReactor(self.r)
        opts.fromBlock(b)
        opts.fromUserSettings(self.cs)

        return dragonExecutor.DragonExecuter(opts, b)


def selectBlocksToRun(o):
    """Choose blocks that will be passed for DRAGON analysis."""
    dragonBlocks = []
    xsGroupManager = o.getInterface("xsGroups")
    for block in xsGroupManager.representativeBlocks.values():
        dragonBlocks.append(block)
    return dragonBlocks
