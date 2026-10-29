"""Compatibility installer for older pip versions without PEP 660 support."""

from setuptools import find_packages, setup


setup(
    # The shorter agent-flight-recorder distribution name is owned by an
    # unrelated project on PyPI. The import and CLI names remain flightrecorder.
    name="flightrecorder-ai",
    version="1.1.1",
    description="A local black-box recorder and failure investigator for AI agents",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Mohamed Ansar",
    license="Apache-2.0",
    url="https://github.com/kmsmohamedansar/agent-flight-recorder",
    project_urls={
        "Source": "https://github.com/kmsmohamedansar/agent-flight-recorder",
        "Issues": "https://github.com/kmsmohamedansar/agent-flight-recorder/issues",
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Debuggers",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    extras_require={
        "mcp": ["mcp>=2.3,<3; python_version >= '3.10'"],
    },
    entry_points={
        "console_scripts": [
            "flightrecorder=flightrecorder.cli:main",
            "flightrecorder-mcp=flightrecorder.mcp_server:main",
        ]
    },
)
