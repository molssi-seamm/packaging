from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import pprint

import semver

from .conda import Conda
from .pip import Pip

core_packages = (
    "molsystem",
    "reference-handler",
    "seamm",
    "seamm-dashboard",
    "seamm-datastore",
    "seamm-exec",
    "seamm-ff-util",
    "seamm-installer",
    "seamm-jobserver",
    "seamm-util",
    "seamm-widgets",
)
molssi_plug_ins = (
    "control-parameters-step",
    "crystal-builder-step",
    "custom-step",
    "diffusivity-step",
    "dftbplus-step",
    "forcefield-step",
    "geometry-analysis-step",
    "fhi-aims-step",
    "from-smiles-step",
    "gaussian-step",
    "lammps-step",
    "loop-step",
    "mopac-step",
    "nwchem-step",
    "packmol-step",
    "properties-step",
    "psi4-step",
    "qcarchive-step",
    "quickmin-step",
    "rdkit-step",
    "read-structure-step",
    "set-cell-step",
    "strain-step",
    "supercell-step",
    "torchani-step",
    "table-step",
    "thermal-conductivity-step",
)
external_plug_ins = []

excluded_plug_ins = (
    "chemical-formula",
    "cms-plots",
    "seamm-dashboard-client",
    "seamm-cookiecutter",
    "cassandra-step",
    "solvate-step",
)
development_packages = (
    "black",
    "codecov",
    "flake8",
    "nodejs",
    "pydata-sphinx-theme",
    "pytest",
    "pytest-cov",
    "pygments",
    "sphinx",
    "sphinx-design",
    "twine",
    "watchdog",
)
development_packages_pip = (
    "build",
    "rinohtype",
    "seamm-cookiecutter",
    "sphinx-copybutton",
    "sphinx-rtd-theme",
    "pystemmer",
)

logger = logging.getLogger("seamm_packages")
logger.setLevel(logging.DEBUG)


def find_packages(progress=True):
    """Find the Python packages in SEAMM.

    Parameters
    ----------
    progress : bool = True
        Whether to print out dots to show progress.

    Returns
    -------
    dict(str, str)
        A dictionary with information about the packages.
    """
    print("Finding all the packages that make up SEAMM. This may take several minutes.")
    pip = Pip()
    conda = Conda()

    # Use pip to find possible packages.
    packages = pip.search(query="SEAMM", progress=progress, newline=False)

    print(f"Found {len(packages)} packages.")

    for package in excluded_plug_ins:
        if package in packages:
            del packages[package]

    # Need to add molsystem and reference-handler by hand
    for package in core_packages:
        if package not in packages:
            tmp = pip.search(query=package, exact=True, progress=True, newline=False)
            logger.debug(f"Query for package {package}\n{pprint.pformat(tmp)}\n")
            if package in tmp:
                packages[package] = tmp[package]

    print(f"After including and excluding packages there are {len(packages)} packages.")

    # Set the type
    for package in packages:
        if package in core_packages:
            packages[package]["type"] = "Core package"
        elif package in molssi_plug_ins:
            packages[package]["type"] = "MolSSI plug-in"
        else:
            packages[package]["type"] = "3rd-party plug-in"

    # Check the versions on conda, and prefer those...
    logger.info("Find packages: checking for conda versions")
    if progress:
        print("", flush=True)

    if True:
        count = 0
        for package, data in sorted(packages.items(), key=lambda x: x[0]):
            count += 1
            print(f"{count}: ", end="")
            logger.info(f"    {package}")
            conda_packages = conda.search(
                f"{package}>={data['version']}", progress=True, newline=False
            )

            if conda_packages is None:
                print(f"\t{package} not in conda-forge")
                continue

            tmp = conda_packages[package]

            print(
                f"\t{package} {data['version']} -> {tmp['version']} ({tmp['channel']})"
            )

            if semver.compare(tmp["version"], data["version"]) != 1:
                print("updating to conda")
                data["version"] = tmp["version"]
                data["channel"] = tmp["channel"]
                if "/conda-forge" in data["channel"]:
                    data["channel"] = "conda-forge"
        if progress:
            print("", flush=True)

    # Convert conda-forge url in channel to 'conda-forge'
    for data in packages.values():
        if "/conda-forge" in data["channel"]:
            data["channel"] = "conda-forge"

    # Read the existing package database and see if there are changes
    message = []
    changed = False
    path = Path("environments") / "SEAMM_packages.json"
    if not path.exists():
        changed = True
        print("The package database does not exist.")

        plist = {
            "date": datetime.now(timezone.utc).isoformat(),
            "doi": "10.5281/zenodo.7860696",
            "packages": packages,
        }
        with path.open("w") as fd:
            json.dump(plist, fd, indent=4, sort_keys=True)
        with Path("commit_message.txt").open("w") as fd:
            fd.write("Initial commit of the SEAMM package database")
    else:
        with path.open("r") as fd:
            try:
                plist = json.load(fd)
            except json.JSONDecodeError:
                plist = None
        if plist is None:
            changed = True
            print("The package database could not be read, so replacing.")

            plist = {
                "date": datetime.now(timezone.utc).isoformat(),
                "doi": "10.5281/zenodo.7860696",
                "packages": packages,
            }
            with path.open("w") as fd:
                json.dump(plist, fd, indent=4, sort_keys=True)
            with Path("commit_message.txt").open("w") as fd:
                fd.write("Could not read the SEAMM package database, so replacing")
        else:
            old_packages = plist["packages"]
            for package in packages:
                print(f"Checking package {package}")
                if package not in old_packages:
                    changed = True
                    print(f"    New package: {package}")
                    message.append(f"{package} added to SEAMM")
                else:
                    oldv = old_packages[package]["version"]
                    newv = packages[package]["version"]
                    oldchannel = old_packages[package]["channel"]
                    newchannel = packages[package]["channel"]
                    oldtype = old_packages[package]["type"]
                    newtype = packages[package]["type"]
                    print(f"    Old version: {oldv} ({oldchannel}) {oldtype}")
                    print(f"    New version: {newv} ({newchannel}) {newtype}")
                    if oldv != newv:
                        changed = True
                        if oldchannel != newchannel:
                            print(
                                f"    Changed package: {package} from {oldv} "
                                f"({oldchannel}) to {newv} ({newchannel})"
                            )
                            message.append(
                                f"{package} changed from {oldv} ({oldchannel}) to "
                                f"{newv} ({newchannel})"
                            )
                        else:
                            print(
                                f"    Changed package: {package} from {oldv} to "
                                f"{newv}"
                            )
                            message.append(
                                f"{package} changed from {oldv} to {newv}"
                            )
                    elif oldchannel != newchannel:
                        changed = True
                        print(
                            f"    Changed channel: {package} from {oldchannel} to "
                            f"{newchannel}"
                        )
                        message.append(
                            f"{package} changed from {oldchannel} to {newchannel}"
                        )
                    if oldtype != newtype:
                        changed = True
                        print(
                            f"    Changed type: {package} from {oldtype} to {newtype}"
                        )
                        message.append(
                            f"{package} changed from {oldtype} to {newtype}"
                        )
            if not changed:
                print("The package database has not changed.")
            else:
                print("The package database has changed.")

                plist = {
                    "date": datetime.now(timezone.utc).isoformat(),
                    "doi": "10.5281/zenodo.7860696",
                    "packages": packages,
                }
                with path.open("w") as fd:
                    json.dump(plist, fd, indent=4, sort_keys=True)
                with Path("commit_message.txt").open("w") as fd:
                    fd.write("New SEAMM package database\n\n")
                    for i, line in enumerate(message):
                        fd.write(f"{i}. {line}\n")

    return changed, packages

def create_env_files(packages):
    """Create the environment files for the packages.

    Parameters
    ----------
    packages : dict(str, dict)
        The packages to create the environment files for.
    """
    print("Creating the environment files for the packages.")
    prelines = [
        """name: seamm
channels:
  - conda-forge
  - defaults
dependencies:
  - pip
  - python

    # From conda-forge because pip can't install
  - psutil
    # The Dashboard fails with newer versions, so until fixed.
  - connexion<3.0

    # Core packages
"""
    ]
    # Creating the environment file with versions pinned
    lines = []
    lines.extend(prelines)
    # Core SEAMM packages
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "Core package" and data["channel"] == "conda-forge":
            lines.append(f"  - {package}=={data['version']}")
    lines.append("")

    lines.append("    # MolSSI plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "MolSSI plug-in" and data["channel"] == "conda-forge":
            lines.append(f"  - {package}=={data['version']}")
    lines.append("")

    lines.append("    # 3rd-party plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "3rd-party plug-in" and data["channel"] == "conda-forge":
            lines.append(f"  - {package}=={data['version']}")
    lines.append("")

    lines.append("    # PyPi packages")
    lines.append("  - pip:")
    lines.append("    # Core packages")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "Core package" and data["channel"] == "pypi":
            lines.append(f"    - {package}=={data['version']}")
    lines.append("")
    lines.append("    # MolSSI plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "MolSSI plug-in" and data["channel"] == "pypi":
            lines.append(f"    - {package}=={data['version']}")
    lines.append("")
    lines.append("    # 3rd-party plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "3rd-party plug-in" and data["channel"] == "pypi":
            lines.append(f"    - {package}=={data['version']}")

    with open("environments/seamm_pinned.yml", "w") as fd:
        fd.write("\n".join(lines))
        print("Wrote environments/seamm_pinned.yml")

    # Creating the environment file with versions not pinned
    lines = []
    lines.extend(prelines)
    # Core SEAMM packages
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "Core package" and data["channel"] == "conda-forge":
            lines.append(f"  - {package}")
    lines.append("")

    lines.append("    # MolSSI plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "MolSSI plug-in" and data["channel"] == "conda-forge":
            lines.append(f"  - {package}")
    lines.append("")

    lines.append("    # 3rd-party plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "3rd-party plug-in" and data["channel"] == "conda-forge":
            lines.append(f"  - {package}")
    lines.append("")

    lines.append("    # PyPi packages")
    lines.append("  - pip:")
    lines.append("    # Core packages")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "Core package" and data["channel"] == "pypi":
            lines.append(f"    - {package}")
    lines.append("")
    lines.append("    # MolSSI plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "MolSSI plug-in" and data["channel"] == "pypi":
            lines.append(f"    - {package}")
    lines.append("")
    lines.append("    # 3rd-party plug-ins")
    for package, data in sorted(packages.items(), key=lambda x: x[0]):
        if data["type"] == "3rd-party plug-in" and data["channel"] == "pypi":
            lines.append(f"    - {package}")

    with open("environments/seamm_pinned.yml", "w") as fd:
        fd.write("\n".join(lines))
        print("Wrote environments/seamm_pinned.yml")
