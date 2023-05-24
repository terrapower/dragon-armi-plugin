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

"""Setup.py script for TerraPower DRAGON ARMI plugin."""

from setuptools import setup

from terrapower.physics.neutronics.dragon.meta import __version__

with open("README.rst") as f:
    README = f.read()

setup(
    name="terrapower-dragon",
    version=__version__,
    description=("ARMI plugin for lattice physics analysis with DRAGON."),
    author="TerraPower LLC",
    author_email="armi-devs@terrapower.com",
    url="https://github.com/terrapower/dragon-plugin",
    packages=[
        "terrapower.physics.neutronics.dragon",
        "terrapower.physics.neutronics.dragon.tests",
    ],
    package_data={
        "terrapower.physics.neutronics.dragon": ["resources/*", "resources/**/*"]
    },
    license="Apache 2.0",
    long_description=README,
    install_requires=["armi", "jinja2"],
    keywords="ARMI, DRAGON",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: Apache Software License",
    ],
    test_suite="tests",
)
