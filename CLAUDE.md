# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## What this is

hos is the distribution: the hackable tools on a bootable live ISO, with
hsmd as init. hos owns the whole assembly — the root filesystem is
populated by xbps from the Void repositories and everything else is hos's:
a static C init in an initramfs hos builds itself (`init/`,
`overlay/usr/bin/hos-mkinitramfs`), the boot and shutdown scripts
(`overlay/etc/hsm/`), the gettys, `halt`/`reboot`/`shutdown`, the ISO
layout and boot menu (`mkiso`), the installer (`hos-install`). Nothing
from void-mklive, dracut, base-system or runit-void is used; Void
supplies packages and the kernel (with its firmware and updates), which
is the part not worth redoing.

Inputs: `PACKAGES` (the whole package list, base included), `SERVICES`
(`/var/service` links), `IGNORE` (xbps ignorepkg, also on installed
systems), `overlay/` (copied verbatim into the rootfs), `init/` (the
initramfs init, ~500 lines of C11), `hos-repo.pub` (the package
repository's key), and the four scripts `mkrootfs`, `mkpkg`, `mkiso`,
`overlay/usr/bin/hos-mkinitramfs` the Makefile drives.

## Build commands

- `make` / `make iso` — the ISO, `hos-<version>-x86_64.iso`. No sudo:
  every step that needs root runs in a user namespace (`unshare --user
  --map-root-user --map-auto --mount`, the `NS` variable; empty when
  already root, as in CI), which needs a `/etc/subuid` line for the
  user. The chain is `rootfs` → `packages` → `stage` → `initramfs` →
  `iso`.
- `make rootfs` — `mkrootfs install`: `xbps-install -r build/rootfs`
  of `PACKAGES` from `REPO` (+nonfree) with `IGNORE` as ignorepkg, the
  repo keys copied from the host, /dev /proc /sys bound into the rootfs
  for the package hooks (the binds die with the namespace). The package
  cache is `build/xbps-cache`. Stamp `build/rootfs/.installed`: reruns
  only when `PACKAGES`, `IGNORE` or `mkrootfs` change; `make clean`
  otherwise.
- `make packages` — `mkpkg`, as the user: builds every sibling in
  `PROJECTS` in its own tree (hed with `BUILD_DIR=build/hos PREFIX=/usr
  MAN_DIR=/usr/share/man`, so its man path is FHS without touching the
  developer's default build), lays each out under `build/pkg/<p>` as it
  installs (`/usr/bin`; hweb's pair in `/usr/lib/hweb` with `/usr/bin/hweb`
  a symlink, since WebKit loads the extension from the real binary's
  directory; hai's skills and tools in `/usr/share/hai`; hnd's dbus
  activation file; hed's man pages), and `xbps-create`s it into
  `build/repo`, indexed by `xbps-rindex`. Plus `hackable-fonts` from
  `fonts/`. Version from `git describe` (`v1.2.0-14-gabc` → `1.2.0.14`,
  untagged → `0.0.0.<count>`, always `_1`), run dependencies computed
  from every ELF's NEEDED sonames looked up in the rootfs (an unowned
  soname is an error: `PACKAGES` lacks a library), plus the hand-kept
  `extradeps` (fzf, curl, the fonts). No xbps-src. Reruns every build,
  it is 40 s. `make sign KEY=…` signs the repo and packages; only
  remote repos need it, so it is CI's last step, after `make iso`.
- `make stage` — `mkrootfs stage` on top of the rootfs, idempotent:
  copies `overlay/`, installs the packages from `build/repo`
  (`xbps-install -f -i`: reinstall, ignore the configured remote repo),
  writes the repo key's trust plist into `/var/db/xbps/keys` (the name
  is the MD5 of the key in ssh form, `ssh-keygen -l -E md5`), rsyncs the
  trees (minus `.git`, hstt's whisper build dir; hos itself too, minus
  `build/`) to `/usr/src/hackable/<p>` for hacking in place (`make
  install` there symlinks into `~/.local/bin`, ahead of the package),
  installs `init/init` as `/usr/lib/hos/init`, fonts,
  backgrounds, the locale (`xbps-reconfigure -f glibc-locales` in a
  chroot), the live user (`hos:hos`, groups, zsh, passwordless sudo in
  `sudoers.d/99-hos`, `/etc/default/live.conf` for hos-install),
  `root:hos`, the `/var/service` links from `SERVICES`, and the version
  into os-release. Rerun after editing anything in `overlay/` or a tool.
- `make initramfs` — `hos-mkinitramfs` against the rootfs's modules and
  `init/init` → `build/initramfs`.
- `make qemu` — boot the newest ISO with kvm, 4 cpus, 4G, on a virtio-vga
  whose preferred mode is the host's primary monitor resolution (xrandr;
  1920x1080 without X), so console and X come up at native size.
- `make vmtest` / `python3 vmtest.py pid1|reboot|install|keep` — boot the newest ISO
  headless under qemu with a freshly built static hsmd, the boot scripts
  and a serial getty injected through `/updates` (a cpio appended to the
  initramfs; the init copies it over the new root), and drive the serial
  console: services up, `sv check`, restart, logs, poweroff; a reboot
  cycle. `install` runs hos-install (injected too, so no ISO rebuild)
  onto a wiped scratch disk under BIOS and EFI and boots it to a login
  at xdm; `keep` does the same into a partition picked at the prompt
  (BIOS), into a partition of a gpt disk with no ESP (EFI: hos makes
  one) and into free space beside an existing ESP with another system's
  fallback loader (EFI, which must survive untouched), and checks the
  partitions it had to leave alone still hold their files. Run
  both after touching hos-install. Needs isoinfo and /dev/kvm. Kernel,
  initramfs and console logs
  land in `build/vm/`. This is the check to run after touching `init/`,
  `overlay/etc/hsm` or hsm.
- Knobs: `VERSION=` (default `git describe`; names the ISO, lands in
  os-release), `REPO=`, `PROJECTS=`, `FONTSRC=`/`BGSRC=` (default the
  vendored `fonts/`, `backgrounds/`), `NS=`.
- `make clean` (inside the namespace, since `build/` is owned by its
  root, i.e. subuids) / `make distclean` (also ISOs).
- Host needs: xbps, rsync, cpio, zstd, squashfs-tools, grub,
  grub-x86_64-efi, xorriso, mtools, python3, and the tools' build deps.
  CI (`.github/workflows/iso.yml`) runs as root in
  `ghcr.io/void-linux/void-glibc-full` (privileged, for the binds),
  installs those plus `PACKAGES` as the build deps, clones every project
  in `PROJECTS` from github.com/42dotmk (one that fails to clone is
  left out with a warning), bumps the latest `v*` tag, creates the
  release with `gh`, signs `build/repo` with the `XBPS_PRIVKEY` secret
  (the private half of `hos-repo.pub`; the author keeps the local copy
  under `~/.config/hos/`) and deploys it to GitHub Pages:
  https://42dotmk.github.io/hos is the package repository
  (`overlay/etc/xbps.d/10-hos-repository.conf`), `pages/index.html`
  its front page. Releases carry the ISO, Pages the packages.

## Architecture

- **Boot path.** grub (grub-mkrescue: BIOS + EFI, hybrid MBR so `dd` to
  a stick works) → `/boot/vmlinuz` (Void's kernel, copied out of the
  rootfs) + `/boot/initramfs` with `hos.live=HOS init=/usr/bin/hsmd` →
  `init/init` mounts devtmpfs/proc/sys/run, loads `config.h`'s module
  list, then does what udev's coldplug does — matches every
  `/sys/bus/*/devices/*/modalias` against `modules.alias` and
  `finit_module`s the hits — until a block device carries an iso9660
  volume labelled `HOS` (or, with `root=UUID=|LABEL=|/dev/`, an ext4
  root): the medium goes on `/run/hos/medium`, its `hos.sfs` on a loop
  device on `/run/hos/sfs`, a tmpfs overlay over that becomes `/`,
  `/updates` is copied in, `/run` and friends are moved, switch_root,
  exec init. ~500 lines, no libraries, no shell in the initramfs (a
  failure prints why and waits; ctrl-alt-del reboots). `hos.debug` on
  the cmdline logs every module and device; the grub menu has an entry
  for it.
- **The initramfs** is `hos-mkinitramfs`: the init plus every module
  under the block-related directories in its `dirs` list (all of
  ata/scsi/usb/nvme/mmc/virtio/pci/phy, the filesystems), closed over
  `modules.dep`, with `modules.alias` filtered to those modules, stored
  uncompressed (Void ships `.ko.zst` but the kernel's own decompressor
  is built for gzip only, so `finit_module` on the compressed file
  fails with EINVAL; the archive as a whole is zstd, so nothing is
  lost); `find | cpio | zstd`. The same script, shipped, is what
  `/etc/kernel.d/post-install/20-hos-initramfs` runs on an installed
  system when xbps updates the kernel (`/boot/initramfs-<ver>.img`, the
  name grub-mkconfig looks for), so hos never needs dracut — `IGNORE`
  holds it back, since `linux-base` depends on it.
- **hsmd is init.** `init=/usr/bin/hsmd`; as pid 1 hsmd runs
  `overlay/etc/hsm/boot` (pseudo filesystems, static-node modules and
  modules-load.d, udev coldplug, keymap/font/rtc from `/etc/rc.conf`,
  fsck + remount + `mount -a` for a disk root — skipped on the overlay —
  swap, utmp, lo, hostname, sysctl, dmesg log, rc.local), supervises
  `/var/service` (a real directory of symlinks into `/etc/sv`, runit's
  layout, so runit's `sv` works — hsmd keeps each service's
  `supervise/`), and on `hsm poweroff|reboot|halt`, ctrl-alt-del or a
  signal stops everything, runs `overlay/etc/hsm/shutdown` (rc.shutdown,
  hwclock, udev exit, pkill, umount, sync) and calls reboot(2).
  `overlay/usr/bin/{halt,poweroff,reboot,shutdown}` are hos's wrappers
  around `hsm`. Service logs are under `/var/log/hsm/NAME/`. Runit is
  not init and never was pid 1 here; the `runit` package stays for `sv`
  and `chpst`.
- **What replaced runit-void**: `overlay/etc/sv/agetty-tty{1,2,S0}`
  (run script without chpst — hsmd already gives each service its own
  session; `conf` holds `GETTY_ARGS`, tty1's has `-a hos` for the live
  autologin, hos-install seds it out), `overlay/etc/rc.conf`,
  `/etc/hostname`, `/etc/locale.conf`. Two ttys is simply two services
  in `SERVICES`, no `down` files.
- **Live user** is baked into the rootfs at stage (`useradd` in a
  chroot), not created at boot; `/etc/skel` (overlay: `.xinitrc` = `exec
  hwm`, a stub `.zshrc`, backgrounds) is what it gets. The live session
  starts from `overlay/etc/profile.d/zz-hos-startx.sh` on tty1 (agetty
  autologin), not exec'd so an X exit drops to a shell. The `zz-`
  matters: Void's `locale.sh` in profile.d exports LANG, and X must
  inherit it.
- **An installed hos logs in at xdm** (in `PACKAGES` with xrdb,
  xsetroot, pam_rundir; not in `SERVICES` - the live ISO keeps the
  autologin). hos-install links Void's own `/etc/sv/xdm` (its `log/`
  wants runit-void's vlogger; hsmd ignores `log/` dirs, as for dbus and
  NetworkManager) and removes `zz-hos-startx.sh`, or every console login
  would start a second X. `overlay/etc/X11/xdm`: `xdm-config` (Void's,
  pointed at hos's `Xsession` and `Xsetup_0`, no XDMCP), `Xservers`
  (`:0` on vt7), `Xresources` (the greeter in Iosevka and the splash
  colours), `Xsetup_0` (the ground: hbg with `HOME=/usr/share/hos/xdm`,
  so its own bgdir resolves to `overlay/usr/share/hos/xdm/pictures/
  backgrounds/preffered/base42.png` - 42.mk's BASE42 logo,
  https://42.mk/img/base.svg, rendered once onto 1920x1080 in the
  splash colours, low on the screen under the centred box; hbg's
  picture dies with hbg, so it keeps running behind the greeter),
  `Xstartup_0` (root, after a good login: `pkill -x -u root hbg`, or
  hwm's `pgrep -x hbg ||` would skip the user's own, then Void's
  GiveConsole; a non-zero exit there refuses the login),
  `Xsession` (as the user: `/etc/profile`, then `~/.xsession` or
  `~/.xinitrc` - what startx runs, so both ways in start the same
  session - else hwm, under `dbus-run-session` when no bus is set; F1 at
  the greeter is the failsafe hterm). `overlay/etc/pam.d/xdm` is Void's
  with `pam_rundir` for `pam_elogind` (no elogind here): the session gets
  `/run/user/UID` and `XDG_RUNTIME_DIR`, which pipewire needs.
- **Shell and tmux defaults are system-wide**, not in skel: zsh reads
  `overlay/etc/zsh/zshrc`, which sources `zshrc.d/*.zsh` (options,
  completion + fzf bindings, keys, prompt, env with the toolchain PATHs
  and fasd, aliases, git aliases, functions, hai's keys,
  autosuggestions/highlighting last), before `~/.zshrc`; tmux reads
  `overlay/etc/tmux.conf` before the user's. The zsh side is the
  author's shared dotfiles (`~/.dotfiles/zsh`, never its untracked
  `personal/`) merged into those files, not shipped beside them: sync
  by merging again. Aliases lean on `PACKAGES` (bat, eza, xsel, fzf,
  ripgrep, pass, tmux, hed) and the vendored `overlay/usr/bin/fasd`
  (MIT, Void has no package); one for a tool hos does not ship is
  guarded with `$+commands[...]`, so it appears once the tool is
  installed and never breaks the command it shadows. hos sets
  `extended_glob`, so key names in `bindkey` must be quoted (an unquoted
  `^o` is a glob). `/etc/zsh/completions` (`_pass`) goes ahead of the
  packaged completions.
- **hos-install** (`overlay/usr/bin`, ~250 lines of sh, no menus):
  the target is a whole disk (wiped: sfdisk gpt + ESP under EFI, dos
  otherwise), a partition (only it is formatted), or `-f DISK` (a
  partition appended in the largest `sfdisk -F` area); no argument lists
  disks and free space and asks. On a partition or free space under EFI
  the disk's existing ESP is mounted, never formatted, and grub's
  `--removable` copy goes on only when the ESP has no
  `EFI/BOOT/BOOTX64.EFI` yet (an existing one is another system's; hos
  then boots by the NVRAM entry grub-install makes). Before anything is
  written it lists the ESP's `EFI/` directories and asks whether to
  format it for a clean start (default no; `-E` is yes), after which it
  counts as hos's own. Every phase is timed: the table is printed at
  the end and kept in `/var/log/hos-install.times`. A disk that has no ESP (EFI), or is gpt with no BIOS boot
  partition (BIOS), gets one made in its largest free area (off the
  front of hos's area with `-f`); no room refuses before writing, as
  does a dos table without enough free primaries.
  No os-prober: other systems on the disk are not in hos's grub menu.
  Then mkfs, `tar
  --one-file-system` of the live root onto the target (so everything
  staged lands there; the medium under /run is another fs), fstab by
  UUID, the live user and its autologin/sudoers/`live.conf` removed,
  xdm enabled in their place (and tty1's startx profile script gone),
  USER created in the live user's groups (its home then chowned and
  seeded from skel regardless: `useradd -m` leaves a pre-existing home
  alone, and X dies on `.Xauthority` in one the user cannot write),
  passwords set with `chpasswd -c SHA512` and checked in
  `/etc/shadow` (plain `chpasswd` on Void goes through PAM, whose
  chpasswd stack is `pam_permit`: exit 0, nothing set - mkrootfs's
  `root:hos` was never set that way until it got `-c` too),
  `hos-mkinitramfs` per kernel in the target, grub with
  `--bootloader-id=hos` plus `--removable`, `grub-mkconfig` reading
  `overlay/etc/default/grub` (`init=/usr/bin/hsmd`). The installed
  system boots through the same init with `root=UUID=`; its boot script
  then fscks and mounts fstab. Interactive on purpose (type the disk
  name, root's and USER's passwords), but every question comes before
  the copy, so the rest runs unattended. The EFI branch has not run on
  hardware.
- **Install speed.** The copy is bound by squashfs decompression, so
  `mkiso` packs zstd-19 rather than xz (~5% bigger, ~8x faster to read
  on one core) and the init mounts it `threads=percpu` (falling back to
  a plain mount). The initramfs rebuild is ~2 s and not worth reusing
  the ISO's.
- **hos-setup** (`overlay/usr/bin`, sh, run by the user after the
  first login; hos-install's last line says so): `timezone` (fzf over
  zone1970.tab; `TIMEZONE=` in `/etc/rc.conf`, which the boot script
  turns into `/etc/localtime`, plus the link now), `gpg` (import a
  secret key file, ownertrust 6 on each primary fingerprint - pass
  cannot encrypt to an untrusted key - then `git clone` the password
  store), `hai` (writes `~/.config/hackable/hai.conf`: url, model,
  `keycmd = pass show ENTRY`; shows `haid --check`'s url/model/key),
  `service` (`~/.config/hsm/sv/haid/run` = `exec haid -r` for the
  session hsmd hwm starts; `hsm rescan` + `hsm check` when it runs),
  `voice` (what `hai talk` needs and the ISO cannot carry: `make voice`
  in /usr/src/hackable/hai for piper and its voice, `make model
  MODEL=small|large-v3-turbo` in /usr/src/hackable/hstt, then `model =`
  in `~/.config/hackable/hstt.conf`, since hstt defaults to large; the
  URLs stay in those makefiles, not here).
  Status before and after, explanations per step, next steps at the
  end. Tested with stand-ins for sudo/fzf/pgrep/hsm/make in a scratch
  HOME (mind gpg's keyboxd: one started for an earlier scratch home
  answers for the next, and a fresh home then lists the old keys).
- CI clones every tool from github.com/42dotmk: hai is there too
  (42dotmk/hai, public, the same history as halicea/hai; the local
  clone pushes to both remotes, `origin` and `42dotmk`). A tool that
  exists only elsewhere is silently left out of the release, with just
  a warning annotation on the run.
- **sudo under X** asks through hmenu: `SUDO_ASKPASS=/usr/bin/hmenu-askpass`
  (sudo does not search PATH for it) and `alias sudo='sudo -A'` only when
  `$DISPLAY` is set - on a console hmenu cannot show. hmenu's three
  scripts (`hmenu-xbps` for Cmd+I, `hmenu-pass`, `hmenu-askpass`) are
  packaged beside the binary by mkpkg; without them Cmd+I listed nothing.
- Branding: `overlay/etc/os-release` and `overlay/etc/issue`; fastfetch
  reads `ID=hos` but has no logo for it, so
  `overlay/etc/fastfetch/config.jsonc` points it at
  `overlay/usr/share/hos/logo.txt` (that config must also carry the
  default `modules` list, or fastfetch prints only the logo). The boot
  menu background `splash.png` is rendered from the same logo by
  `splash.py` (a Makefile rule); mkiso's grub.cfg uses it via gfxterm.
- Fonts: hterm, htray and hnd name the family "Iosevka Nerd Font Mono"
  in their config.h and resolve it through fontconfig (hterm via
  fc-match, so `fontconfig` is in `PACKAGES`); the `hackable-fonts`
  package from `fonts/` puts the files in `/usr/share/fonts/hackable`
  and stage primes the system cache with `fc-cache -s`. Nothing under
  `/home` is staged any more (a root-owned `/home/halicea` once broke
  installs for a user of that name).
  hbg's config.h reads `~/pictures/backgrounds/preffered`; stage gives
  `/etc/skel` and `/root` the `backgrounds/` picks (squashfs dedups the
  copies; keep them few and small).
- hwm's autostart list is spawned via `/bin/zsh -c`, so zsh must be in
  `PACKAGES` — without it hbg, htray and hnd silently never start.
- Keep `PACKAGES` honest: base + runtime libs + toolchain + the -devel
  headers needed to rebuild every tool on the running system. No
  editors, no vi. `IGNORE` is for dependency-chain fat only — never
  something a shipped binary links against (xbps aborts on an
  unresolvable shlib). All linux-firmware stays.
- The rootfs, squashfs and ISO steps must run in the same uid mapping
  (all under `NS`), or the squashfs would carry subuids. Files in
  `build/` are owned by the namespace's root, hence `clean` runs there.
- This repo is NOT in the root Makefile's PROJECTS fan-out on purpose —
  an ISO build wants the network and minutes, so it stays manual.
