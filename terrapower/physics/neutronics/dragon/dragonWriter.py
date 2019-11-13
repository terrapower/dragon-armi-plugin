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
Writes DRAGON inputs during an ARMI run.
"""
import os

from armi import interfaces
from armi.utils import units
from armi.nucDirectory import nuclideBases
from armi.physics import neutronics
from armi import runLog
from armi.utils import pathTools

from . import dragonTemplateHelper

N_CHARS_ALLOWED_IN_LIB_NAME = 8


class DragonWriter(interfaces.InputWriter):
    """
    Responsible for writing DRAGON input files based on a template.

    Notes
    -----
    By default points to the only template provided with the DRAGON plugin. User
    can optionally point to a template helper module, which will allow pointing to
    other templates, and customization of "bookkeeping" code to execute to augment
    the template data before rendering the template. This can be helpful since almost
    all but the simplest new templates will likely need some sort of new values to 
    insert into the template.
    """

    def __init__(self, o, block, cs, nucsToModel, xsId, fuelTempInK):
        """
        Initialize a writer for this block.

        Parameters
        ----------
        o : Operator
            The ARMI operator instance. This is not used anywhere within the writer.
            Only included to send to the DragonTemplateHelper for maximum flexibility.
        block : Block
            The ARMI block object to process into template data.
        cs : Settings
            The case settings of the current ARMI run.
        nucsToModel : list of str
            Strings that are keys of nuclideBases.byName to get the
        xsId : string
            A two character string representing the cross section identification. The
            first character typically represents the cross section group, and the 
            second is the burnup group. Burnup group is a charactor that represents a
            range of burnup values which are considered to be similar enough enough
            to use the same microscopic cross sections (ISOTXS file). For example,
            burnup group a is the lowest burnup group, so it might be 0 to 2% burnup.
        fuelTempInK : float
            The temperature of the fuel in Kelvin.
        """
        interfaces.InputWriter.__init__(self, cs=cs)
        # o should not be used by this class.
        # Only included to pass on to DragonTemplateHelper, so that template creators
        # have access to everything.
        self._o = o
        self.b = block
        self.nucsToModel = nucsToModel
        self.xsId = xsId
        self.xsSettings = self.cs[neutronics.const.CONF_CROSS_SECTION][xsId]
        self.fuelTempInK = fuelTempInK

    def write(self, fName=None):
        """
        Write a DRAGON input file.

        Parameters
        ----------
        fName : str
            The (optional) name of the input to write.

        Returns
        -------
        inputName : inputName
            Name of input file produced.
        """
        runLog.info(
            f"Writing DRAGON input for xsID: {self.xsId} based on block: {self.b}"
        )

        Klass = self._getTemplateHelperClass()  # pylint: disable=invalid-name
        # give the helper everything the writer has access to.
        templateHelper = Klass(self, self._o)
        # This allows for custom template data definition as needed by users.
        templateData = self._buildBasicTemplateData()
        templateData = templateHelper.updateTemplateData(templateData)

        template = templateHelper.readTemplate()
        inputName = fName or f"dragon{self.xsId}.x2m"
        with open(inputName, "w") as dragonInput:
            dragonInput.write(template.render(**templateData))

        return inputName

    def _buildBasicTemplateData(self):
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
        innerBoundaries = units.GROUP_STRUCTURE[self.cs["groupStructure"]][1:]
        dragonLibName = os.path.basename(self.cs["dragonDataPath"])

        # a data class could be used here, but considering an external python script
        # will augment this, a simple dictionary is more flexible.
        templateData = {
            "xsId": self.xsId,
            # Last chars of default library name are typically more meaningful.
            # EG: draglibendfb7r1SHEM361
            "nucData": dragonLibName[-N_CHARS_ALLOWED_IN_LIB_NAME:],
            "nucDataComment": self.cs["dragonDataPath"],  # full path
            "tempFuelInKelvin": self.fuelTempInK,
            "blockNDensCard": blockNDensCard,
            "tempComponentsInKelvin": componentTemp,
            "componentNDensCard": componentNDensCard,
            "buckling": self.xsSettings.criticalBuckling,
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
        nucs = self.nucsToModel

        nDensCardData = []
        mixtureMassDensity = armiObj.density()
        numberDensities = armiObj.getNuclideNumberDensities(nucs)
        totalADensityModeled = sum(numberDensities)
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
                    f"{nuclideBase.label}{self.xsId}",
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

    def _getTemplateHelperClass(self):
        """Return a user customized template helper based on DragonTemplateHelper."""
        if self.cs["dragonTemplateHelper"] is None:
            return dragonTemplateHelper.DragonTemplateHelper
        try:
            mod, className = pathTools.separateModuleAndAttribute(
                self.cs["dragonTemplateHelper"]
            )
            userSpecifiedHelperModule = pathTools.importCustomPyModule(mod)
        except Exception as err:
            raise ImportError(
                f"Was not able to import {self.cs['dragonTemplateHelper']}."
            ) from err
        return userSpecifiedHelperModule.__dict__[className]
