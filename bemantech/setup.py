from setuptools import setup, find_packages

import os

req_file = os.path.join(os.path.dirname(__file__), "bemantech", "requirements.txt")
with open(req_file) as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in bemantech/__init__.py
from bemantech import __version__ as version

setup(
	name="bemantech",
	version=version,
	description="Custom ERPNext App for Bemantech",
	author="Tariqul Islam",
	author_email="tariqmolla8@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
