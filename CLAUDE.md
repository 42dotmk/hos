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
- `make clean` / `make distclean` (also removes ISOs).

## Architecture

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
  Iosevka files to the same path in the rootfs, plus
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
