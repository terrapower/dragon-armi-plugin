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
Handles DRAGON template interactions during an ARMI run.
"""
import os

from jinja2 import Template

THIS_DIR = os.path.dirname(__file__)


class DragonTemplateHelper:
    """
    Responsible for pointing to the template and customization of template data.

    Notes
    -----
    This module is responsible to pointing to the path of the template to be used for a
    particular ARMI xsId. It also give the user the ability to change or add
    data to the templateData dictionary right before it is inserted into the template.
    """

    def __init__(self, writer, o):
        self.o = o
        self.b = writer.b
        self.nucsToModel = writer.nucsToModel
        self.cs = writer.cs
        self.xsSettings = writer.xsSettings
        self.xsId = writer.xsId
        self.fuelTempInK = writer.fuelTempInK

    def readTemplate(self):
        """Read the Template."""
        with open(self.getTemplatePath()) as templateFormat:
            return Template(templateFormat.read())

    # no-self-use disabled since children's implementation will use self
    def getTemplatePath(self):  # pylint: disable=no-self-use
        """
        Return the path to the template for the associated xsId.

        Notes
        -----
        This allows for different templates for each xsId as needed.
        """
        # Absolute paths are best. If doing relative path, must be relative to ARMI
        # run location (which for testing is the tests folder).
        return os.path.join(THIS_DIR, "resources", "DRAGON_Template_0D.txt")

    def updateTemplateData(self, templateData):  # pylint: disable=no-self-use
        """
        Make any last minute changes/additions to the template data before insertion.

        Notes
        -----
        For no changes, just `return templateData` is sufficient.
        """
        return templateData
