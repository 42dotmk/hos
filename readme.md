# hos

hackable os. the hackable tools as a bootable live iso, from the kernel
up: hos's own init, initramfs, boot scripts, service manager (hsmd as
pid 1), boot menu and installer; the packages and the kernel come from
the void linux repositories through xbps, the one part not worth
redoing. two ttys, only the essential services, every hackable tool
as a package with its full source tree at /usr/src/hackable — edit,
make, run, on the running system.

## build

    make            # hos-<version>-x86_64.iso, no sudo
    make rootfs     # just the package install into build/rootfs
    make packages   # the tools as xbps packages into build/repo
    make stage      # overlay, packages, sources, user, services on top
    make initramfs  # hos's init + block drivers -> build/initramfs
    make qemu       # boot the newest iso with kvm
    make vmtest     # boot it headless, hsmd as init, check services/reboot/poweroff

needs a void linux host (xbps) with rsync, cpio, zstd, squashfs-tools,
grub, grub-x86_64-efi, xorriso, mtools, python3, and the build deps of
the tools themselves — the sibling trees are built in place first, then
snapshotted. nothing runs as root: the steps that need it run in a user
namespace (`unshare --map-auto`, so your user needs a line in
/etc/subuid). the package cache lives in build/, so a rebuild only
downloads what changed.

## what's on it

- a base hos picks itself (PACKAGES: coreutils, util-linux, eudev, kmod,
  shadow, sudo, xbps, ...), void's kernel with all firmware,
  xorg-minimal, dbus, networkmanager; gettys only on tty1/tty2
- hsm as init: hsmd is pid 1, runs hos's boot script, supervises
  /var/service and shuts the machine down; `hsm status`, `hsm restart
  foo`, `poweroff`, `reboot` work, and so does runit's `sv check foo` —
  hsmd speaks runit's supervise/ protocol
- hos's initramfs: a static c init (init/) that loads the drivers the
  hardware asks for, finds the iso by label, mounts its squashfs under
  a tmpfs overlay and switches root. no dracut, no udev in there
- every hackable tool as an xbps package (mkpkg builds them from the
  trees, versioned from git, dependencies computed from what they link);
  the same packages are published signed at https://42dotmk.github.io/hos,
  which /etc/xbps.d names, so `xbps-install -Su` updates the tools with
  the rest of the system — on the iso, on an install, or on plain void
- every project's working tree under /usr/src/hackable too (no git
  history); hos itself as well, so the iso carries its own recipe
- gcc/make/pkg-config/git/cmake + the -devel headers each tool needs,
  so the sources rebuild in place
- iosevka nerd font mono (the hackable-fonts package) under
  /usr/share/fonts/hackable, where fontconfig finds it for every tool
- no vi, no vim, no editors but hed

## on the live system

- hostname `hos`; user `hos` (password `hos`, passwordless sudo) is
  autologged in on tty1; root is `root:hos`
- `startx` — .xinitrc execs hwm, which autostarts htray, hnd, and hbg
- hstt ships without a whisper model and without whisper.cpp's 379M
  build dir; `make model` and `make` in /usr/src/hackable/hstt on the
  live system fetch and rebuild
- hacking in place: make in /usr/src/hackable/<tool>, then make install
  symlinks the result into ~/.local/bin, ahead of the package on PATH
- hweb finds hweb-ext.so next to the resolved binary — the package puts
  both in /usr/lib/hweb with /usr/bin/hweb a symlink to it
- the boot menu has entries for no kernel modesetting, a serial console,
  and an init that logs every module and device it touches

## installing to disk

    sudo hos-install [-u USER] [-H HOSTNAME] /dev/sdX

- wipes the disk (it asks you to type the device name), makes a root
  filesystem (and an EFI system partition when booted from EFI), copies
  the live root onto it as-is — the packages, /usr/src/hackable,
  skel, enabled services — and writes fstab by UUID
- undoes the live bits: the `hos` user, its autologin on tty1 and its
  passwordless sudo go; USER is created in the same groups with zsh,
  .xinitrc and the backgrounds from /etc/skel (wheel gets sudo); root
  and USER passwords are asked
- builds the initramfs with hos-mkinitramfs (the same init, now with
  root=UUID=) and installs grub; /etc/default/grub carries
  `init=/usr/bin/hsmd`, so the installed system boots hsmd as pid 1
  like the live one. kernel updates from the void repos rebuild the
  initramfs through /etc/kernel.d
- ~130 lines of sh in overlay/usr/bin/hos-install, no menus; keymap,
  timezone and wifi are yours afterwards (rc.conf, /etc/localtime, nmcli)

## inputs

- `PACKAGES` — everything xbps installs, base included (no base-system,
  no runit-void, no dracut)
- `SERVICES` — what /var/service links to
- `IGNORE` — packages held back with xbps ignorepkg, on the iso and on
  installed systems: dracut, and dependency-chain fat nothing on the
  iso links against (OpenCL stack, python via gi-docgen, perl). all
  firmware stays, so it boots on any machine
- `overlay/` — copied verbatim into the rootfs: os-release/issue
  branding, hsm's boot/shutdown scripts, the gettys, rc.conf,
  halt/reboot/shutdown, hos-mkinitramfs and its kernel hooks,
  hos-install, /etc/default/grub, .xinitrc
- `init/` — the initramfs init, one c file and a config.h
- `mkrootfs`, `mkpkg`, `mkiso` — the steps the Makefile drives; `hos-repo.pub`
  the package repository's key (CI holds the private half)
