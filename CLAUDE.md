# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## What this is

hos is the distribution: Void Linux + the hackable tools as a bootable
live ISO. There is no C here — the deliverable is `hos-*.iso`, produced
by `make` from four inputs: `PACKAGES` (xbps packages installed on top
of base-system), `SERVICES` (runit services enabled beyond base
defaults), `IGNORE` (packages held back via xbps ignorepkg), and
`overlay/` (files copied verbatim into the ISO rootfs).

## Build commands

- `make` / `make iso` — full ISO build. Clones void-mklive into
  `build/` on first run; the mklive.sh step runs under sudo and keeps
  its xbps package cache in `build/xbps-cachedir-x86_64`, so rebuilds
  don't re-download. Claude can't run this step itself (sudo needs a
  tty password) — the user runs it.
- `make stage` — assemble `build/overlay` only (build all sibling
  projects in place, snapshot their trees, plant the /usr/bin symlinks
  and fonts). No root; use it to inspect what would land on the ISO.
- `make qemu` — boot the newest ISO with kvm.
- `make vmtest` / `python3 vmtest.py pid1|reboot|runit` — boot the newest
  ISO headless under qemu with a freshly built static hsmd and the
  init-related overlay files injected (the initrd copies `/updates` over
  the live root before pivoting, so no ISO rebuild and no root), and
  drive the serial console: services up, `sv check`, restart, logs,
  poweroff; a reboot cycle; and the runit-as-init fallback. Needs
  isoinfo and /dev/kvm. Kernel, initrd and console logs land in
  `build/vm/`.
- Overridable knobs, all for CI: `SUDO=` when already root, `VERSION=`
  (default `git describe`; names the ISO and lands in os-release as
  VERSION_ID), `FONTSRC=` / `BGSRC=` (default the repo's vendored `fonts/` and
  `backgrounds/`), `PROJECTS=`.
- `make clean` / `make distclean` (also removes ISOs).

## Architecture

- **hsmd is init.** The kernel command line (`-C` in the Makefile) ends
  with `init=/usr/bin/hsmd`; dracut takes the last `init=` and hands the
  rest of the command line to init as arguments (hsmd ignores them as
  pid 1). hsmd runs `overlay/etc/hsm/boot` (Void's
  `/etc/runit/core-services` minus the runit-control one, plus the
  `/run/runit/runsvdir/current` link that `/var/service` resolves
  through, plus rc.local), supervises `/var/service` — still runit's
  layout, so `SERVICES` and `/etc/sv` are unchanged — and on
  `hsm poweroff|reboot|halt` or ctrl-alt-del runs
  `overlay/etc/hsm/shutdown` (Void's `shutdown.d` minus the `sv` stop)
  and calls reboot(2). Service logs are under `/var/log/hsm/NAME/`.
  Overlay replacements for runit's tools: `usr/bin/sv` (forwards to
  `hsm`, which is what makes `sv check dbus` in Void's run scripts work),
  `usr/bin/halt` (+ `reboot`/`poweroff` symlinks) and `usr/bin/shutdown`,
  all of which fall back to `runit-init` when runit is pid 1. That
  fallback is real: `overlay/etc/runit/2` makes hsmd runit's stage 2, so
  booting with `init=/sbin/init` still gives a hos with hsm, and
  `overlay/etc/runit/shutdown.d/10-sv-stop.sh` is neutralized for it.
  These overlay files overwrite package-owned ones (runit, runit-void);
  on the ISO that is fine, on an installed system a package update
  restores them until hos ships its own package.
- Sibling projects are built in their own trees first, then rsynced
  (minus `.git` and hstt's `vendor/whisper.cpp/build`) into the overlay
  at `usr/src/hackable/<p>`; `/usr/bin` symlinks point into those trees,
  mirroring the workspace's ~/.local/bin convention. hweb depends on
  this: it locates `hweb-ext.so` next to the resolved binary.
- Branding: `-T "hos linux"` for the boot menu; `overlay/etc/os-release`
  and `overlay/etc/issue` replace Void's (the overlay is copied after
  mklive drops in its own `data/issue`). fastfetch reads `ID=hos` from
  os-release for the OS line but has no logo for it and would fall back
  to `ID_LIKE=void`'s, so `overlay/etc/fastfetch/config.jsonc` (the
  system-wide config path) points it at `overlay/usr/share/hos/logo.txt`.
  That config must also carry the default `modules` list: a fastfetch
  config without one prints the logo and nothing else. The boot menu
  background is `splash.png`, rendered from the same logo by `splash.py`
  (a Makefile rule) and handed to mklive via the `SPLASH_IMAGE` env var —
  there is no CLI flag for it, hence `sudo env`. Locale is `-l $(LOCALE)`,
  en_US.UTF-8 like the user's machine. The live user is created at
  boot by mklive's dracut module `dracut/vmklive/adduser.sh`, which
  hardcodes hostname `void-live` and password `voidlinux`; the Makefile
  seds those to `hos` once after cloning (`build/void-mklive/.hos-patched`
  stamp). `live.user=hos live.autologin` on the kernel cmdline does the
  rest.
- Two-tty rule: `overlay/etc/sv/agetty-tty{3..6}/down` are runit `down`
  files masking the extra gettys, rather than fighting base-system's
  defaults.
- `overlay/etc/dracut.conf.d/hos.conf` omits dracut's `drm` module:
  mklive runs dracut non-hostonly inside the rootfs chroot after the
  overlay is copied, and `drm` would pull ~140M of nvidia/amdgpu/i915
  firmware into the initramfs where a live ISO never needs it.
- hterm's config.h compiles in absolute font paths under
  `/home/halicea/.local/share/fonts`; stage copies exactly those four
  Iosevka files (vendored in `fonts/`) to the same path in the rootfs, plus
  `/usr/share/fonts/hackable` so fontconfig finds "Iosevka NFM" for
  htray/hnd/hmenu.
- hbg's config.h reads `~/pictures/backgrounds/preffered`; stage copies
  the `BGS` picks from the user's copy of that directory into
  `/etc/skel` (so useradd -m gives the live user a set) and `/root`.
  Keep it to a few small files — squashfs dedups the two copies, but
  each pick still costs its size on the ISO.
- The live session starts via `overlay/etc/skel/.xinitrc` (and
  `overlay/root/.xinitrc`): just `exec hwm` — hwm autostarts htray, hnd,
  and hbg itself. `overlay/etc/profile.d/zz-hos-startx.sh` runs startx
  from the tty1 login shell (agetty autologin), not exec'd so an X exit
  drops to a shell instead of relogging into X forever; tty2 stays a
  plain login. The `zz-` matters: /etc/profile sources profile.d in
  name order and Void's `locale.sh` is what exports LANG, so a hook
  sorting before it starts X in the C locale.
- The login shell is zsh: `live.shell=/bin/zsh` on the cmdline for the
  live user, `overlay/etc/default/useradd` for users created later.
  `overlay/etc/skel/.zshrc` (and `root/.zshrc`) exist so a first login
  gets a prompt instead of zsh-newuser-install. Void's zsh sources
  /etc/profile from its zprofile, so profile.d (LANG, startx) still runs.
- hwm's autostart list is spawned via `/bin/zsh -c`, so zsh must be in
  `PACKAGES` even though the login shell is bash — without it hbg,
  htray and hnd silently never start while launching them by hand works.
- Keep `PACKAGES` honest: runtime libs + toolchain + the -devel headers
  needed to rebuild every tool on the running system. No editors, no vi.
- `IGNORE` is for dependency-chain fat only — never something a shipped
  binary links against. To find candidates: `xbps-install -n` dry-run
  of base-system + PACKAGES against a repo index ranks installed sizes,
  `xbps-query -X <pkg>` shows who pulls it. All linux-firmware stays.
- Every path handed to mklive.sh must be absolute: xbps resolves a
  relative `-c` cachedir against the install rootdir, which for the
  target is inside the image tree — the first build shipped 1.3G of
  `.xbps` files on the ISO that way.
- This repo is NOT in the root Makefile's PROJECTS fan-out on purpose —
  an ISO build wants sudo and network, so it stays manual.
- `.github/workflows/iso.yml` builds and releases the ISO on every push
  to main (and on dispatch, with a major/minor/patch choice). It runs in
  void-mklive's own privileged container like Void's CI, installs
  `PACKAGES` as the build deps, clones every project in `PROJECTS` from
  github.com/42dotmk (so all of them must be pushed there), bumps the latest `v*` tag
  and creates the release with `gh`. A build is ~1.7G, so releases are
  the distribution channel, not artifacts.
