"""The system libraries the Linux packages declare, for the packages and tests.

Copied from os_specific/linux/build_packages.sh, which built the packages
before Bazel: OpenGL, GLib, D-Bus, fonts, the X11/XCB/Wayland libraries of
Qt's platform plugins, and the CA certificates for HTTPS. RPM_SONAMES are
library names, so the rpm installs on Fedora, RHEL/Rocky/Alma and openSUSE,
whose package names differ.
"""

DEB_DEPENDS = [
    "ca-certificates",
    "libdbus-1-3",
    "libegl1",
    "libfontconfig1",
    "libfreetype6",
    "libgl1",
    "libglib2.0-0",
    "libwayland-client0",
    "libwayland-cursor0",
    "libwayland-egl1",
    "libx11-6",
    "libx11-xcb1",
    "libxext6",
    "libxrender1",
    "libxkbcommon0",
    "libxkbcommon-x11-0",
    "libxcb1",
    "libxcb-glx0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-shm0",
    "libxcb-sync1",
    "libxcb-util1",
    "libxcb-xfixes0",
    "libxcb-xinerama0",
    "libxcb-xkb1",
]

RPM_SONAMES = [
    "libdbus-1.so.3",
    "libEGL.so.1",
    "libfontconfig.so.1",
    "libfreetype.so.6",
    "libGL.so.1",
    "libglib-2.0.so.0",
    "libgthread-2.0.so.0",
    "libwayland-client.so.0",
    "libwayland-cursor.so.0",
    "libwayland-egl.so.1",
    "libX11.so.6",
    "libX11-xcb.so.1",
    "libXext.so.6",
    "libXrender.so.1",
    "libxkbcommon.so.0",
    "libxkbcommon-x11.so.0",
    "libxcb.so.1",
    "libxcb-glx.so.0",
    "libxcb-icccm.so.4",
    "libxcb-image.so.0",
    "libxcb-keysyms.so.1",
    "libxcb-randr.so.0",
    "libxcb-render.so.0",
    "libxcb-render-util.so.0",
    "libxcb-shape.so.0",
    "libxcb-shm.so.0",
    "libxcb-sync.so.1",
    "libxcb-util.so.1",
    "libxcb-xfixes.so.0",
    "libxcb-xinerama.so.0",
    "libxcb-xkb.so.1",
]

BASE_SYSTEM_LIBRARIES = [
    "ld-linux-x86-64.so.2",
    "libc.so.6",
    "libdl.so.2",
    "libgcc_s.so.1",
    "libm.so.6",
    "libpthread.so.0",
    "libresolv.so.2",
    "librt.so.1",
    "libstdc++.so.6",
    "libutil.so.1",
]
"""glibc's own libraries and the C++ runtime, which every supported
distribution installs with its base system."""
