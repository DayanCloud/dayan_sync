"""Describe our module distribution to Distutils."""
from setuptools import find_packages, setup


def parse_requirements(filename):
    with open(filename, "r") as f:
        for line in f:
            yield line.strip()


setup(
    name="dayan_sync",
    author="Shenzhen Rayvision Technology Co., Ltd",
    author_email="developer@rayvision.com",
    url="https://github.com/internal/dayan_sync",
    package_dir={"": "."},
    packages=find_packages("."),
    description=("Upload configuration file and asset file, download result "
                 "file."),
    entry_points={},
    install_requires=list(parse_requirements("requirements.txt")),
    package_data={
        'dayan_sync': ["./transmission/*", "./transmission/*/*", "./transmission/*/*/*", "./transmission/*/*/*/*", "*.ini"],
    },
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
)
