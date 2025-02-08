import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

exec(open("LXST/_version.py", "r").read())

setuptools.setup(
    name="lxst",
    version=__version__,
    author="Mark Qvist",
    author_email="mark@unsigned.io",
    description="Lightweight Extensible Signal Transport for Reticulum",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/markqvist/lxst",
    packages=["LXST", "LXST.Utilities"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    entry_points= {
        'console_scripts': [
            'rnphone=LXST.Utilities.rnphone:main',
        ]
    },
    install_requires=["rns>=0.9.1",
                      "soundcard",
                      "numpy",
                      "pycodec2"],
    python_requires=">=3.7",
)