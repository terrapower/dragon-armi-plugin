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

This uses templates and attempts to do most of the logic in code
to build the appropriate data structures. Then, the template engine
is responsible for transforming that data into the format required
for DRAGON to process it as input.

Classes here are intended to be specialized with more design-specific
subclasess in design-specific ARMI apps (or other clients).
"""

from collections import namedtuple

from jinja2 import Template

from armi.utils import units
from armi.nucDirectory import nuclideBases
from armi import runLog
from armi.reactor.flags import Flags


N_CHARS_ALLOWED_IN_LIB_NAME = 8

MixtureNuclide = namedtuple(
    "MixtureNuclide", ["armiName", "dragName", "xsid", "ndens", "selfshield"]
)


class DragonWriter:
    """
    Write a DRAGON input file using a template.

    This base class should strive to avoid any design-specific assumptions.
    """

    def __init__(self, armiObjs, options):
        """
        Initialize a writer.

        Parameters
        ----------
        armiObjs : list
            The ARMI object(s) to process into template data. These represent the parts of
            a reactor you want to model.
        options : DragonOptions
            Data structure that contains execution and modeling controls
        """
        self.armiObjs = armiObjs
        self.options = options

    def __str__(self):
        return f"<DragonWriter for {str(self.armiObjs)[:15]}...>"

    def write(self):
        """
        Write a DRAGON input file.
        """
        runLog.info(f"Writing input with {self}")

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
        Return data to be sent to the template to produce the DRAGON input.
        """
        templateData = {
            "xsId": self.options.xsID,
            "nucData": self.options.libDataFileShort,
            "nucDataComment": self.options.libDataFile,  # full path
            "groupStructure": self._makeGroupStructure(),
        }
        return templateData

    def _makeGroupStructure(self):
        """
        Make energy group structure bounds.

        DRAGON only needs group boundary values between 0 and the max. It assumes lowest
        boundary is 0 eV and the upper most boundary is the highest energy fine group boundary
        in the specified library.
        """
        return units.GROUP_STRUCTURE[self.options.groupStructure][1:]


class DragonWriterHomogenized(DragonWriter):
    """
    Write DRAGON inputs with homogenized compositions.

    This subclass assumes that the DRAGON case will represent one or 
    more armi objects.

    The current implementation is capable of writing MIX cards for multiple
    compositions at once but does not yet have the ability to write geometry
    representation for anything beyond 0-D.
    """

    def _buildTemplateData(self):
        templateData = DragonWriter._buildTemplateData(self)

        templateData.update(
            {
                "mixtures": self._makeMixtures(),
                "buckling": self.options.xsSettings.criticalBuckling,
            }
        )
        return templateData

    def _makeMixtures(self):
        """Make a DragonMixture from each object slated for inclusion in the input."""
        return [
            DragonMixture(obj, self.options, i) for i, obj in enumerate(self.armiObjs)
        ]


class DragonMixture:
    """
    Data structure for a single mixture in Dragon.

    Each mixture has:
        * A temperature
        * A number density vector
        * A mapping between library names and internal nuclide names
        * A self-shielding vector

    """

    def __init__(self, armiObj, options, index):
        self.armiObj = armiObj
        self.options = options
        self.index = index

    def getTempInK(self):
        """
        Return the mixture temperature in Kelvin.

        Notes
        -----
        Only 1 temperature can be specified per mixture in DRAGON. For 0-D
        cases, the temperature of the fuel component is used for the entire
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
        if any(self.armiObj.doChildrenHaveFlags(Flags.FUEL)):
            typeSpec = Flags.FUEL
        else:
            typeSpec = None
        for fuel in self.armiObj.iterComponents(typeSpec):
            vol = fuel.getArea()
            avgNum += fuel.temperatureInC * vol
            avgDenom += vol
        return units.getTk(Tc=avgNum / avgDenom)

    def getMixVector(self):
        """
        Generate mixture composition table.
        """
        nucs = self.options.nuclides
        nucData = []
        numberDensities = self.armiObj.getNuclideNumberDensities(nucs)
        if not any(numberDensities):
            # This is an empty armiObj. Can happen with zero-volume dummy components.
            # This this writer's job is to accurately reflect the state of the reactor,
            # we simply return an emtpy set of number densities.
            return nucData
        for nucName, nDens in zip(nucs, numberDensities):
            nuclideBase = nuclideBases.byName[nucName]
            if isinstance(
                nuclideBase,
                (nuclideBases.LumpNuclideBase, nuclideBases.DummyNuclideBase),
            ):
                # This skips lumped fission products.
                continue

            nucData.append(
                MixtureNuclide(
                    armiName=nuclideBase.label,
                    xsid=self.options.xsID,
                    dragName=getDragLibNucID(nuclideBase),
                    ndens=nDens,
                    selfshield=self.getSelfShieldingFlag(nuclideBase, nDens),
                )
            )
        return nucData

    # pylint: disable=unused-argument
    def getSelfShieldingFlag(self, nucBase, nDens) -> str:
        """
        Get self shielding flag for a given nuclide.

        Figuring out how to structure resonant region index (inrs)
        requires some engineering judgment, and this structure allows template
        creators to apply their own judgment.
        There is some basic data that templates filter out of
        self shielding (SS) calculation, or apply different inrs to nuclides.

        Need index to make sure each mixture gets different fine-group flux.
        """
        if nucBase.isHeavyMetal() or self.armiObj.density() > 0.0001:
            return f"{self.index + 1}"
        return ""


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
