# Unofficial PyMOL(TM) Python wheel files
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-blue.svg)](https://GitHub.com/urban233/pymol-open-source-whl/graphs/commit-activity)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![GitHub issues](https://img.shields.io/github/issues/urban233/pymol-open-source-whl)](https://GitHub.com/urban233/pymol-open-source-whl/issues/)

### Supported Platforms

![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)

This repository offers **unofficial** binary wheels for the open-source version of PyMOL(TM)
for **all major** operating systems.
These wheel files are intended for use in a Python project.
If you are searching for PyMOL as ready-to-use application, see
[distribution/](distribution/README.md) (formerly
[pymol-open-source-setup](https://github.com/kullik01/pymol-open-source-setup)).

## Contents of this document
* [About PyMOL](#About-PyMOL)
* [Contents of this repository](#Contents-of-this-repository)
* [Install](#Install)
* [Build wheel file](#Build-wheel-file)
    * [Prerequisites](#Prerequisites)
    * [Build and test](#Build-and-test)
    * [Release wheels](#Release-wheels)
* [License](#License)
* [Acknowledgements](#Acknowledgements)
<!--* [References and useful links](#References-and-useful-links) -->

## About PyMOL
[PyMOL™](https://pymol.org/) is a powerful visualization software for rendering and animating 3D molecular structures. PyMOL is a trademark of Schrödinger, LLC.

Please note that the files provided here are **unofficial**. They are informal, unrecognized, and unsupported, offered for testing and evaluation purposes only. No warranty or liability is provided, and the software is made available "as-is."

## Contents of this repository
This repository is a fork of [schrodinger/pymol-open-source](https://github.com/schrodinger/pymol-open-source)
and combines two former repositories with their full git history:

| Path | Content | Former repository |
|------|---------|-------------------|
| `/` (everything except `distribution/`) | PyMOL sources and the wheel build | [urban233/pymol-open-source-whl](https://github.com/urban233/pymol-open-source-whl) |
| `distribution/` | Ready-to-run apps: Windows installer, macOS DMGs, Linux packages ([README](distribution/README.md)) | [kullik01/pymol-open-source-setup](https://github.com/kullik01/pymol-open-source-setup) |

The history of `distribution/` was rewritten into that folder; each of its commits names the
original commit in an `Original-commit:` line. Wheel releases use `v*` tags, app releases
`setup-v*` tags. Updates from Schrödinger arrive by syncing the fork's `master` branch and
merging it into `production`.

The wheel is built with [Bazel](https://bazel.build/) from the upstream source layout in
place: the `BUILD.bazel` files beside the sources, `MODULE.bazel` for the pinned native
dependencies (FreeType, GLEW, GLM, libpng, libxml2, netCDF, zlib and the NumPy C headers,
all fetched and built by Bazel) and `tools/bazel/` for the build rules and Bazel tests.

## Install
To install PyMOL run:
```shell
pip install pymol-open-source-whl
```

## Build wheel file
`pip install .` does not build PyMOL: the compiled extensions come from Bazel, and the
in-tree build backend stops with instructions instead of producing a wheel without them.

### Prerequisites
- [Bazelisk](https://github.com/bazelbuild/bazelisk), on `PATH` as `bazel` or `bazelisk`;
  it fetches the Bazel version `.bazelversion` names.
- A C++17 compiler: Visual Studio 2022 Build Tools (Windows), the Xcode command line tools
  (macOS), or GCC with the OpenGL development headers (Linux, e.g. `mesa-libGL-devel`).
- On Windows, Developer Mode (Settings > System > For developers), which lets Bazel create
  the symlinks its Python tests need.
- [uv](https://docs.astral.sh/uv/) for the development environment.

### Build and test
Run from the repository root:

1. Sync the development environment:
    ```shell
    uv sync --locked
    ```

2. Build this platform's wheel for the running Python (or pass `python=3.X`):
    ```shell
    ./pymake.bat build_wheel     # Windows
    ./pymake.sh build_wheel      # macOS/Linux
    ```
    The wheel is written to `bazel-bin/tools/bazel/wheel/`. Bazel can build it directly too:
    ```shell
    bazel build //tools/bazel/wheel:wheel --@rules_python//python/config_settings:python_version=3.12
    ```

3. Build, install and test the wheel for the running Python:
    ```shell
    ./pymake.bat test  # Windows
    ./pymake.sh test   # macOS/Linux
    ```
    This runs the tests under `tests/` against the installed wheel.

4. Run the Bazel tests (wheel metadata and layout, generated shader headers, native import):
    ```shell
    bazel test //...
    ```

Machine-local Bazel options go into an ignored `user.bazelrc` at the repository root.

### Release wheels
Pull requests are checked by the Bazel workflow (`bazel build //...` and `bazel test //...`
on all four platforms, CPython 3.10). The full wheel matrix is built only before a release:

1. Push a branch `release-stage/<version>` (for example `release-stage/3.2.0.4`) with the
   release's changes and open its pull request into `production`. Every push to it runs
   the Build Wheels workflow.
2. When it is green and merged, tag the release `v<version>`; the tag builds, validates
   and publishes the wheels.

A manual run (Actions > Build Wheels > Run workflow) builds the matrix for any branch.

The Build Wheels workflow builds twenty wheels: CPython 3.10 to 3.14 for Windows x64,
macOS arm64, macOS x86_64 and Linux x86_64 (manylinux_2_28). Each wheel is repaired where
its platform needs it (delvewheel bundles the MSVC C++ and OpenMP runtimes on Windows,
auditwheel bundles libgomp on Linux), installed into a clean environment, and tested with
`scripts/test_wheel.py` against both the minimum compatible NumPy 2 and the latest NumPy 2.
Mandatory coordinate and volume array tests must pass; missing or skipped native NumPy
tests fail the build. The minimum is NumPy 2.2.0 for Python 3.10-3.13 and NumPy 2.3.3 for
Python 3.14. CI retains separate JUnit reports for each wheel and NumPy version, including
failed runs. Release validation still requires all twenty Python/platform wheels before
publication.

Wheels are compiled against the NumPy 2.2 C headers of their platform and require NumPy 2
at runtime; there is no separate NumPy 1 variant. These checks cover headless package and
NumPy interoperability, not GUI behavior or every operating system version.

## License
Copyright (c) [Schrodinger, LLC](https://www.schrodinger.com/)

Published under a BSD-like license, see [LICENSE](LICENSE).

## Acknowledgements
**Schrödinger** for being the driving force behind the continued development of PyMOL after Warren's passing, ensuring that the open-source version remained alive and well.

**NOTE**: the following list has not been updated since Fall 2003.  
Since then, the PyMOL effort has grown to such an extent that it is no longer
practical to recognize everyone individually.  Fortunately, a public
record of participation exists and can be appreciated on the internet,
and especially via the PyMOL mailing list archives.  Suffice it to say
that the PyMOL user community now numbers well into the thousands and
includes scientists, students, and educators worldwide, spread
throughout academia and the biotechnology and pharmaceutical
industries.  Though DeLano Scientific LLC specifically supports and
maintains the PyMOL code base, the project can only continue to
succeed through the sponsorship and participation of the broader
community.

**Founder and Principal Author**:

      Warren L. DeLano 

Major Authors (5000+ lines of code):

      Ralf W. Grosse-Kunstleve (SGLite Module)

Minor Authors (500+ lines of code):

      Scott Dixon (Metaphorics CEX support)
      Filipe Maia (Slice Objects)

Other Contributors: These are the people who have gone out of
their way to help the project with their ideas, actions,
advice, hardware donations, testing, information, sponsorship,
peer support, or code snippets.

      Daan van Aalten
      Paul Adams 
      Stephen Adler
      Jun Aishima 
      Dennis Allison
      Ricardo Aparicio
      Daniel Appelman   
      Diosdado "Rey" Banatao
      Michael Banck
      Ulrich Baumann
      Joseph Becker
      Balaji Bhyravbhatla
      Jeff Bizzaro
      Jeff Blaney 
      Juergen Bosch 
      Michael Bower
      Sarina Bromberg
      Axel Brunger
      Robert Campbell
      Bronwyn Carlisle 
      Duilio Cascio
      Julien Chiron 
      Shawn Christensen
      Scott Classen
      David Cooper
      Larry Coopet
      Jacob Corn
      Ben Cornett
      Andrew Dalke 
      Koen van der Drift 
      Harry Dailey
      Byron DeLaBarre
      Bill DeGrado
      Thomas Earnest
      Nathaniel Echols
      John Eksterowicz
      Erik Evensen
      David Fahrney
      Tim Fenn
      Thierry Fischmann
      Michael Ford
      Esben Peter Friis
      Kevin Gardner
      R. Michael Garavito
      John Gerig
      Jonathan Greene
      Michael Goodman  
      Joel Harp
      Reece Hart
      Richard Hart
      Peter Haebel
      Matt Henderson
      Douglas Henry 
      Possu Huang 
      Uwe Hoffmann
      Jenny Hinshaw
      Carly Huitema
      Bjorn Kauppi
      Greg Landrum
      Robert Lawrence Kehrer 
      Tom Lee
      Eugen Leitl
      Ken Lind
      Jules Jacobsen
      Luca Jovine
      Andrey Khavryuchenko
      David Konerding
      Greg Landrum
      Michael Love 
      Tadashi Matsushita
      Genevieve Matthews 
      Gerry McDermott 
      Robert McDowell
      Gustavo Mercier      
      Naveen Michaud-Agrawal
      Aaron Miller
      Holly Miller
      Tim Moore
      Kelley Moremen
      Hideaki Moriyama
      Nigel Moriarty 
      Geoffrey Mueller
      Cameron Mura
      Florian Nachon 
      Hanspeter Niederstrasser 
      Michael Nilges
      Hoa Nguyen
      Shoichiro Ono
      Chris Oubridge
      Andre Padilla
      Jay Pandit
      Ezequiel "Zac" Panepucci
      Robert Phillips
      Hans Purkey
      Rama Ranganathan
      Michael Randal
      Daniel Ricklin 
      Ian Robinson
      Eric Ross
      Kristian Rother
      Marc Saric
      Bill Scott
      Keana Scott
      Denis Shcherbakov
      Goede Schueler
      Paul Sherwood
      Ward Smith
      John Somoza
      David van der Spoel
      Paul Sprengeler
      Matt Stephenson 
      Peter Stogios
      John Stone
      Charlie Strauss
      Michael Summers
      Brian Sutton
      Hanna and Abraham Szoke
      Rod Tweten
      Andras Varadi
      Scott Walsh
      Pat Walters
      Mark White
      Michael Wilson
      Dave Weininger
      Chris Wiesmann
      Charles Wolfus
      Richard Xie

Miscellaneous Code Snippets Lifted From:

      Thomas Malik (fast matrix-multiply code)
      John E. Grayson (Author of "Python and Tkinter")
      Doug Hellmann (Wrote code that JEG later modified.)

Open-Source "Enablers" (essential, but not directly involved):

      Brian Paul (Mesa)
      Mark Kilgard (GLUT)
      Guido van Rossum (Python)
      Linus Torvalds (Linux Kernel)

      Precision Insight (DRI)
      The XFree86 Project (Free Windowing System)
      VA Linux (CVS Hosting)
      Richard Stallman/Free Software Foundation (GNU Suite)
      The unknown authors of EISPACK (Linear Algebra)

Graphics Technology "Enablers" (essential!)

      3dfx (RIP)
      nVidia 
      ATI

### Specific Acknowledgments:

* Thanks to Joni W. Lam for making the business work.

* Thanks to John Stone and John Furr for being such excellent
  colleagues.

* Thanks to Ragu Bharadwaj and Marcin Joachimiak for Java expertise
  and encouragement.

* Thanks to Apple Computer for continued encouragement, assistance,
  and HLAs in support of Mac development.  Thanks especially to
  Robert Kehrer for creating so many fun opportunities over the years.

* Thanks to Aaron Miller (GlaxoSmithKline) for a continuous stream of
  thoughtful opinions and suggestions.

* Thanks to Dave Weininger for suggesting the "roving" feature and for
  being such an inspirational friend and mentor.

* Thanks to Matt Hahn and Dave Rogers for proving that it can also be
  done, again.

* Thanks to Mick Savage for providing experienced practical advice on
  the marketing of scientific software.

* Thanks to Ian Matthew for 3D experience and perspective.

* Thanks for Jeff Blaney for numerous insightful discussions.

* Thanks to Elizabeth Pehrson for making this a team effort.

* Thanks to Erin Bradley for schooling in focus and vision.

* Thanks to Vera Povolona for catalytic clarity and introspection.

* Thanks to Anthony Nichols for proving that it can be done, yet again.

* Thanks to Thompson Doman for timely Open-Source validation.

* Thanks to Manfred Sippl for making it all seem so simple.

* Thanks to Kristian Rother for all his excellent work building on the
  PyMOL foundation, and in helping others learn to use the software.

* Thanks to Dave Weininger, Scott Dixon, Roger Sayle, Andrew Dalke,
  Anthony Nichols, Dick Cramer, and David Miller, as well as rest of
  the Daylight and OpenEye teams for thoughtful discussions on PyMOL
  and open-source software during my 2002 pilgrimage to Sante Fe, NM.

* Thanks to Ralf Grosse-Kunstleve for his contribution of the "sglite"
  space group and symmetry handling module.

* Thanks to the scientists and management of Sunesis Pharmaceuticals
  for supporting PyMOL development since program inception.

* Thanks to the Computational Crystallography Initiative (LBNL)
  developers for their encouragement, ideas, and support.

* Thanks to Scott Walsh for being the first individual to provide
  financial support for PyMOL.

* Thanks to the hundreds of individuals, companies, and institutions
  that have provided financial support for the project.

* Thanks to Brian Paul and the Precision Insight team for development
  of Mesa/DRI which greatly assisted in the early development of PyMOL.

* Thanks to Michael Love for the first major outside port of PyMOL
  (to GNU-Darwin/OSX) and for believing in the cause.

* Thanks for Paul Sherwood for making a concerted effort to develop
  using PyMOL long before the software and vision had matured.

* Thanks to Jay Ponder for thoughtful email discussions on Tinker and
  the role of open-source scientific software.

* Thanks to hundreds of PyMOL users for the many forms of feedback,
  bug sightings, and encouragement they've provided.
