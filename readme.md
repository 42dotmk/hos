# hos

hackable os. void linux + the hackable tools as a bootable live iso.
two ttys, only the essential services, every hackable tool compiled and
symlinked into /bin with its full source tree at /usr/src/hackable —
edit, make, run, on the running system.

## build

    make            # hos-YYYYMMDD-x86_64.iso (the mklive step uses sudo)
    make stage      # just assemble what would land on the iso, no root
    make qemu       # boot the newest iso with kvm
    make vmtest     # boot it headless, hsmd as init, check services/reboot/poweroff

needs a void linux host with xbps, git, rsync, and the build deps of the
tools themselves — the sibling trees are built in place first, then
snapshotted. the xbps package cache lives in build/, so a rebuild only
downloads what changed.

## what's on it

- base-system + xorg-minimal, dbus, networkmanager; gettys only on
  tty1/tty2
- hsm as init: hsmd is pid 1, runs void's boot scripts, supervises the
  usual /var/service and shuts the machine down; `hsm status`, `hsm
  restart foo`, `sv check foo`, `poweroff`, `reboot` all work. runit
  stays installed as a fallback (boot with init=/sbin/init)
- every project from the hackable workspace under /usr/src/hackable
  (working-tree snapshot, no git history), binaries symlinked into /bin
- gcc/make/pkg-config/git/cmake + the -devel headers each tool needs,
  so the sources rebuild in place
- iosevka nerd font mono at hterm's compiled-in path and under
  /usr/share/fonts/hackable for the xft tools
- no vi, no vim, no editors but hed

## on the live system

- hostname `hos`; user `hos` (password `hos`, passwordless sudo) is
  autologged in on tty1; root is `root:hos`
- `startx` — .xinitrc execs hwm, which autostarts htray, hnd, and hbg
- hstt ships without a whisper model and without whisper.cpp's 379M
  build dir; `make model` and `make` in /usr/src/hackable/hstt on the
  live system fetch and rebuild
- hweb finds hweb-ext.so next to the resolved binary — the /bin symlink
  into the source tree is load-bearing, keep it

## inputs

- `PACKAGES` — installed on top of base-system
- `SERVICES` — runit services enabled beyond the defaults
- `IGNORE` — packages held back with xbps ignorepkg: dependency-chain
  fat nothing on the iso links against (OpenCL stack, python via
  gi-docgen, perl, nvi). all firmware stays, so it boots on any machine
- `overlay/` — copied verbatim into the rootfs: os-release/issue
  branding, the tty down files, .xinitrc, hsm's boot/shutdown scripts
  and the sv/halt/shutdown replacements, and a dracut drop-in that
  keeps GPU firmware out of the initramfs
