%{!?project_version:%global project_version 0.7.1}
%{!?snapshot_release:%global snapshot_release 33.gitcb5fcd2}
%{!?commit:%global commit cb5fcd20550deb90fa4a406eed7ea83f8443b90a}
%{!?shortcommit:%global shortcommit cb5fcd2}
%{!?gst_version:%global gst_version 1.26.0}

Name:           libcamera
Version:        %{project_version}
Release:        %{snapshot_release}%{?dist}
Summary:        Camera support library for Linux with RkISP1 support
License:        LGPL-2.1-or-later AND CC0-1.0
URL:            https://libcamera.org
Source0:        %{name}-%{commit}.tar.gz

BuildRequires:  meson >= 1.0.1
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig
BuildRequires:  python3-devel
BuildRequires:  boost-devel
BuildRequires:  libyaml-devel
BuildRequires:  openssl-devel
BuildRequires:  systemd-devel
# Ensures we pull the custom GStreamer development files
BuildRequires:  gstreamer-devel = %{gst_version}

Requires:       gstreamer = %{gst_version}
Requires:       libyaml
Requires:       boost-system
Requires:       boost-filesystem

%description
libcamera %{version} built from commit %{commit}, configured for Comet camera
devices with GStreamer integration, the RkISP1 pipeline, the rkisp1 and simple
IPA modules, and the V4L2 compatibility layer.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       gstreamer-devel = %{gst_version}

%description devel
Headers, pkg-config metadata, and linker symlinks for building software against
the Comet libcamera package installed under /opt/libcamera.

%prep
%autosetup -n %{name}-%{commit}

%build
export CCACHE_DISABLE=1
# Force Meson to find our custom GStreamer first
export PKG_CONFIG_PATH=/opt/gstreamer/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}

meson setup builddir \
  --prefix=/opt/libcamera \
  --libdir=lib64 \
  --buildtype=release \
  -Dgstreamer=enabled \
  -Dpipelines=rkisp1 \
  -Dipas=rkisp1,simple \
  -Dcam=disabled \
  -Dqcam=disabled \
  -Ddocumentation=disabled \
  -Dv4l2=enabled

meson compile -C builddir %{?_smp_mflags}

%install
DESTDIR=%{buildroot} meson install -C builddir

# Hard-Fail Validation: Ensure critical binaries were actually built
test -f %{buildroot}/opt/libcamera/lib64/libcamera/ipa/ipa_rkisp1.so || { echo "FATAL: ipa_rkisp1.so missing"; exit 1; }
test -f %{buildroot}/opt/libcamera/lib64/gstreamer-1.0/libgstlibcamera.so || { echo "FATAL: libgstlibcamera.so missing"; exit 1; }

# Architecture Fix: Relocate the GStreamer plugin so it is natively discovered
install -d %{buildroot}/opt/gstreamer/lib64/gstreamer-1.0
mv %{buildroot}/opt/libcamera/lib64/gstreamer-1.0/libgstlibcamera.so %{buildroot}/opt/gstreamer/lib64/gstreamer-1.0/
rm -rf %{buildroot}/opt/libcamera/lib64/gstreamer-1.0

install -d %{buildroot}%{_sysconfdir}/profile.d
cat > %{buildroot}%{_sysconfdir}/profile.d/libcamera.sh <<'EOF'
if [ -z "${_COMET_LIBCAMERA_SETUP_DONE:-}" ]; then
  export PKG_CONFIG_PATH=/opt/libcamera/lib64/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}
  export LD_LIBRARY_PATH=/opt/libcamera/lib64:/opt/gstreamer/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
  export _COMET_LIBCAMERA_SETUP_DONE=1
fi
EOF

install -d %{buildroot}%{_sysconfdir}/ld.so.conf.d
cat > %{buildroot}%{_sysconfdir}/ld.so.conf.d/libcamera.conf <<'EOF'
/opt/libcamera/lib64
EOF

%files
%license COPYING.rst LICENSES/*
/opt/libcamera/
# Explicitly track the relocated plugin so RPM uninstalls it cleanly
/opt/gstreamer/lib64/gstreamer-1.0/libgstlibcamera.so
%exclude /opt/libcamera/include
%exclude /opt/libcamera/include/*
%exclude /opt/libcamera/lib64/pkgconfig
%exclude /opt/libcamera/lib64/pkgconfig/*
%exclude /opt/libcamera/lib64/*.so
%{_sysconfdir}/profile.d/libcamera.sh
%{_sysconfdir}/ld.so.conf.d/libcamera.conf

%files devel
/opt/libcamera/include/
/opt/libcamera/lib64/pkgconfig/
/opt/libcamera/lib64/*.so

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%changelog
* Mon May 25 2026 Mecha Camera Build <build@mecha.local> - %{version}-%{release}
- Package RkISP1 libcamera build from commit %{commit}.
- Relocated libgstlibcamera.so directly to GStreamer plugin directory.
- Removed GST_PLUGIN_PATH overrides to rely on native discovery.
- Added explicit IPA and plugin validation checks.