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
Write DRAGON inputs based on data contained in ARMI objects.
"""

from jinja2 import Template

from armi.utils import units
from armi.nucDirectory import nuclideBases
from armi import runLog
from armi.reactor.flags import Flags


N_CHARS_ALLOWED_IN_LIB_NAME = 8


class DragonWriter:
    """
    Write DRAGON input file based on a template.

    Makes a 0D cross section case by default.

    Notes
    -----
    Customize the template and the template data collecting for more sophisticated cases.
    """

    def __init__(self, block, options):
        """
        Initialize a writer for this block.

        Parameters
        ----------
        block : Block
            The ARMI block object to process into template data.
        options : DragonOptions
            Data structure that contains execution and modeling controls
        """
        self.b = block
        self.options = options

    def write(self):
        """
        Write a DRAGON input file.
        """
        runLog.info(f"Writing DRAGON input based on: {self.b}")

        templateData = self._buildTemplateData()
        template = self._readTemplate()
        with open(self.options.inputFile, "w") as dragonInput:
            dragonInput.write(template.render(**templateData))

    def _readTemplate(self):
        """Read the template file."""
        with open(self.options.templatePath) as templateFormat:
            return Template(templateFormat.read())

    def _buildTemplateData(self):
        """
        Return a dictionary to be sent to the template to produce the DRAGON input.
        """
        blockNDensCard = self._getDragonNDensCard(self.b)

        # Smallest outer dimension first.
        # See component getBoundingCircleOuterDiameter which is used by __lt__.
        orderedComponents = sorted(self.b)
        componentTemp = tuple(
            units.getTk(Tc=c.temperatureInC) for c in orderedComponents
        )
        componentNDensCard = tuple(
            self._getDragonNDensCard(c) for c in orderedComponents
        )

        # DRAGON only needs inner boundaries it assumes lowest boundary is 0 ev
        # and the upper most boundary is the highest energy fine group boundary in the
        # specified library.
        innerBoundaries = units.GROUP_STRUCTURE[self.options.groupStructure][1:]

        # a data class could be used here, but considering an external python script
        # will augment this, a simple dictionary is more flexible.
        templateData = {
            "xsId": self.options.xsID,
            "nucData": self.options.libDataFileShort,
            "nucDataComment": self.options.libDataFile,  # full path
            "tempFuelInKelvin": self._getFuelTempInK(),
            "blockNDensCard": blockNDensCard,
            "tempComponentsInKelvin": componentTemp,
            "componentNDensCard": componentNDensCard,
            "buckling": self.options.xsSettings.criticalBuckling,
            "groupStructure": innerBoundaries,
            "components": orderedComponents,
            "block": self.b,  # include block so that templates have some flexibility
        }
        return templateData

    def _getDragonNDensCard(self, armiObj):
        """
        Write the armi object as a number density for DRAGON.

        Parameters
        ----------
        armiObj : ArmiObject
            The ARMI object to write data for. ArmiObject, and anything that inherits
            from it implements density and getNuclideNumberDensities.
        """
        nucs = self.options.nuclides

        nDensCardData = []
        mixtureMassDensity = armiObj.density()
        numberDensities = armiObj.getNuclideNumberDensities(nucs)
        totalADensityModeled = sum(numberDensities)
        if not totalADensityModeled:
            # This is an empty armiObj. Can happen with zero-volume dummy components.
            # This this writer's job is to accurately reflect the state of the reactor,
            # we simply return an emtpy set of number densities.
            return nDensCardData
        for nucName, nDens in zip(nucs, numberDensities):
            nuclideBase = nuclideBases.byName[nucName]
            if isinstance(
                nuclideBase,
                (nuclideBases.LumpNuclideBase, nuclideBases.DummyNuclideBase),
            ):
                # DRAGON interface does not currently expand fission products.
                continue

            dragonId = self.getDragLibNucID(nuclideBase)

            # Figuring out how to structure resonant region index (inrs)
            # requires some engineering judgment, and this structure allows template
            # creators to apply their own judgment.
            # There is some basic data that templates filter out of
            # self shielding (SS) calculation, or apply different inrs to nuclides.
            selfShieldingFilterData = {
                # Sometimes very low density components must be filtered from
                # self shielding (by not setting inrs) for the SS to run.
                "mixtureMassDensity": mixtureMassDensity,
                # Heavy metals should almost always have SS.
                "heavyMetal": nuclideBase.isHeavyMetal(),
                # Sometimes it makes sense to filter out minor nuclides from SS.
                "atomFrac": nDens / totalADensityModeled,
            }

            # This density may be 0.0, and DRAGON will run fine.
            nDensCardData.append(
                (
                    f"{nuclideBase.label}{self.options.xsID}",
                    dragonId,
                    nDens,
                    selfShieldingFilterData,
                )
            )
        return nDensCardData

    @staticmethod
    def getDragLibNucID(nucBase):
        """
        Return the DRAGLIB isotope name for this nuclide.
        
        Parameters
        ----------
        nucBase : NuclideBase
            The nuclide to get the DRAGLIB ID for.

        Notes
        -----
        These IDs are compatible with DRAGLIB nuclear data format which is available:
        https://www.polymtl.ca/merlin/libraries.htm
        """
        metastable = nucBase.state
        # DRAGON is case sensitive on nuc names so lower().capitalize() matters.
        dragLibId = f"{nucBase.element.symbol.lower().capitalize()}{nucBase.a}"
        if metastable > 0:
            # Am242m, etc
            dragLibId += "m"
        return dragLibId

    def _getFuelTempInK(self):
        """
        Return the fuel temperature in Kelvin.

        Notes
        -----
        Only 1 temperature can be specified per mixture in DRAGON. For this 0-D
        case, the temperature of the fuel component is used for the entire
        mixture. 

        For heterogeneous models, component temperature should be used.
        Component temperature may not work well yet for non BOL cases since 

        .. warning:: 
            The ARMI cross section group manager does not currently set the
            fuel component temperature to the average component temperatures
            when making a representative block. Thus, for the time being, 
            fuel temperature of an arbitrary block in each representative 
            block's parents will be obtained.
        """
        avgNum = 0.0
        avgDenom = 0.0
        for fuel in self.b.getChildrenWithFlags(Flags.FUEL):
            vol = fuel.getArea()
            avgNum += fuel.temperatureInC * vol
            avgDenom += vol
        return units.getTk(Tc=avgNum / avgDenom)
