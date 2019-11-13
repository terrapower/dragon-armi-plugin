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
import os

from armi import runLog
from armi import interfaces
from armi.utils import units
from armi.nuclearDataIO import isotxs
from armi.physics import neutronics
from armi.physics.neutronics.latticePhysics import latticePhysicsInterface
from armi.nuclearDataIO import xsLibraries
from armi import mpiActions

from . import dragonWriter
from . import dragonExecutor


class DragonInterface(interfaces.Interface):
    """"Schedules activities related to DRAGON during ARMI run."""

    name = "dragon"  # name is required for all interfaces
    function = latticePhysicsInterface.LATTICE_PHYSICS

    def interactBOC(self, cycle=None):
        """Write a DRAGON input and execute it, producing an ISOTXS file."""
        executors = self._writeInputs()
        self._executeDragon(executors)
        self._mergeISOTXS()

    def _writeInputs(self):
        """
        Write the inputs for the representative blocks on the xsGroupManager.
        
        Notes
        -----
        Writing occurs in serial rather than parallel. This is because writing inputs
        depends on the state of the cross section group manager, which only the master
        node has access to. Alternatively, if writing in parallel was desired,
        the reactor state synchronized with the worker nodes, and they could run
        the necessary methods on cross section group manager to get the representative
        blocks. Generally writing inputs is fast, so ARMI typically writes them
        in serial, and executes them in parallel.

        Returns
        -------
        executors : list DragonExecuter
            List of executer actions to run DRAGON in parallel.
        """
        executors = []
        xsGroupManager = self.getInterface("xsGroups")
        for xsId, block in xsGroupManager.representativeBlocks.items():
            fuelTempInK = self._getFuelTempInK(xsId)
            writer = dragonWriter.DragonWriter(
                self.o,
                block,
                self.cs,
                self.r.blueprints.allNuclidesInProblem,
                xsId,
                fuelTempInK,
            )

            inputPath = writer.write()
            executors.append(
                dragonExecutor.DragonExecuter(os.path.abspath(inputPath), xsId)
            )
        return executors

    def _getFuelTempInK(self, xsId):
        """
        Return the fuel temperature in Kelvin.

        Notes
        -----
        The nuclide temperature of fissile/fissionable material is a good estimate
        for fuel temperature.
        This will only be used for a 0 D model since only 1 temperature can be
        specified when there is 1 mixture in DRAGON.
        For heterogeneous models, component temperature should be used.
        Component temperature may not work well yet for non BOL cases since the cross 
        section group manager does not average component temperatures when making a
        representative block.
        """
        # We are not using fuelComponent.p.temperatureInC here because the
        # cross section group manager deepcopies the first block in a group but
        # does not update the temperatures on the components. Using this parameter
        # would be equivalent to using the temperature of a random blocks component
        # with the in cross section group.
        xsGroupManager = self.getInterface("xsGroups")
        # The cross section group manager groups temperatures by nuclide.
        # This order intelligently tries to determine the temperature of the fuel.
        # U238 or Th232 might contain a blanket component so these are preferentially
        # last. If different behavior is desired consider implementing a
        # DragonTemplateHelper.
        for nucName in ("U235", "PU239", "U233", "U238", "TH232"):
            fuelTempInC = xsGroupManager.getNucTemperature(xsId, nucName)

            # specify `is not None` rather than `if fuelTempInC`, since 0 degrees C
            # is valid for a critical experiment.
            if fuelTempInC is not None:
                return units.getTk(Tc=fuelTempInC)

        runLog.warning(
            f"Fuel temperature of xsId {xsId} could not be determined. "
            "Please make sure it has fissionable material if having "
            "access to its fuel temperature is desired.",
            single=True,  # makes it so this warning appears only once per xsId.
        )

        # This will case failure if if the fuel temp ends up being used in the template.
        # If it isn't used, it should be fine, maybe this template has the block driven
        # by another blocks composition.
        return None

    def _executeDragon(self, executors):
        """
        Execute DRAGON on the inputs provided (in parallel).
        
        Parameters
        ----------
        executors : list of DragonExecuter
            DRAGON executors (actions) to execute.
        """
        mpiActions.runActions(self.o, self.r, self.cs, executors, numPerNode=None)

    def _mergeISOTXS(self):
        """Merge all the ISOTXS files together so that can be run for global flux."""

        # Create an empty ISOTXS library to be filled in with XS data
        lib = xsLibraries.IsotxsLibrary()

        neutronVelocities = xsLibraries.mergeXSLibrariesInWorkingDirectory(lib)
        latticePhysicsInterface.setBlockNeutronVelocities(self.r, neutronVelocities)

        isotxs.writeBinary(lib, neutronics.ISOTXS)
