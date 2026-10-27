"""Compatibility installer for older pip versions without PEP 660 support."""

from setuptools import find_packages, setup


setup(
    name="agent-flight-recorder",
    version="1.0.0",
    description="A local black-box recorder and failure investigator for AI agents",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Mohamed Ansar",
    license="Apache-2.0",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={"console_scripts": ["flightrecorder=flightrecorder.cli:main"]},
)
