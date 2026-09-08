# hos

The hackable OS: a small Linux desktop built from the kernel up out of
the [hackable](https://github.com/42dotmk/hackable) tools, with an AI
agent that knows every one of them. It boots from a live ISO into a
tiling desktop in about 300 MB of RAM, ships the source of everything
it runs, and is light enough that the rest of the machine can host
your own language model.

- **Its own OS, not a respin.** The init, the initramfs, the service
  manager that is pid 1, the boot scripts, the boot menu and the
  installer are all hos's, ~1300 lines in total. Void Linux supplies
  the packages and the kernel through xbps, the one part not worth
  redoing. No void-mklive, no dracut, no runit-void, no systemd.
- **The whole desktop is thirteen small C programs.** Window manager,
  terminal, editor, launcher, tray, notifications, browser, mail,
  dictation, service supervisor, AI agent: each a few hundred to a few
  thousand lines, compiled-in configuration, standard protocols
  between them. Most binaries are 40 to 80 KB.
- **An AI that knows its OS.** `hai` is an agent in C for any
  OpenAI-compatible model. On hos it comes with tools and skills for
  the machine it is on: the services, the packages, the windows, the
  browser, the mail, the editor. It reaches you through the desktop's
  notifications and by mail, and you reach it by voice, from a key, a
  terminal, a script or a mail.
- **Hackable in place.** Every tool's source tree is on the ISO under
  `/usr/src/hackable` with the toolchain and headers to rebuild it.
  Edit, `make`, and you are running your change.

## The tools

| Tool | Role on hos |
|---|---|
| [hsm](https://github.com/42dotmk/hsm) | `hsmd` is init (pid 1): runs the boot script, supervises `/var/service` runit-style, shuts the machine down. `hsm` is the client; runit's `sv` works too |
| [hwm](https://github.com/42dotmk/hwm) | Scrollable-column X11 tiling window manager (niri-style layout, dwm-style construction); starts the session's daemons |
| [hterm](https://github.com/42dotmk/hterm) | SDL2 terminal emulator |
| [hed](https://github.com/42dotmk/hed) | Terminal editor, tree-sitter highlighting, vim/emacs/vscode keymaps. The only editor on the ISO: no vi |
| [hmenu](https://github.com/42dotmk/hmenu) | Launcher and window switcher, matching through `fzf` |
| [hws](https://github.com/42dotmk/hws) | Workspace and window overview with live thumbnails |
| [htray](https://github.com/42dotmk/htray) | Tray and status bar (XEmbed) |
| [hnd](https://github.com/42dotmk/hnd) | Notification daemon (org.freedesktop.Notifications) |
| [hbg](https://github.com/42dotmk/hbg) | Background setter and rotator |
| [hweb](https://github.com/42dotmk/hweb) | Vim-like WebKitGTK browser, scriptable over stdin/stdout and a control socket |
| [hml](https://github.com/42dotmk/hml) | Mail: IMAP sync into Maildirs, SMTP send, full-text search index. Local `@hai` addresses are the message bus between you and the agent |
| [hstt](https://github.com/42dotmk/hstt) | Push-to-talk dictation with local whisper.cpp, types into the focused window |
| [hai](https://github.com/42dotmk/hai) | The agent: `haid` holds the conversation and runs the tools, `hai` is the client |

They interoperate only through standard protocols (EWMH, XEmbed,
D-Bus, Maildir, sendmail-shaped SMTP), so any of them can be swapped
for its conventional counterpart and each runs alone on any Linux.

## An OS with an AI in it

hos is built to be operated by an agent as much as by hand, and the
agent is a citizen of the system rather than a chat window on top of
it.

- **It knows the machine.** hai's bundled tools are shell scripts over
  the OS's own commands: `services` (hsm), `packages` (xbps),
  `windows` (hwm's EWMH listing through hmenu), `show` (a URL in hweb,
  a file in hed, a directory in yazi), `browse` (drives hweb), `mail`
  (hml), plus `git`, `search` and `diff`. Its skills are notes on how
  hos is laid out, how services, packages, the desktop, mail and the
  browser work. It reads a project's `CLAUDE.md` or `AGENTS.md` when
  run inside one, and every tool's source is on disk for it to read.
- **It talks through the desktop.** Notifications go through hnd,
  windows are focused through hwm, questions come as a terminal
  prompt, by voice, or as an hmenu yes/no when neither is around.
  Read-only commands run at once; anything that changes the machine
  is confirmed with you first, file edits shown as a diff, and a deny
  list never runs.
- **Mail is the bus.** hai has an address. Mail to `main@hai` (from
  you, a cron job, a script, another agent) lands in a Maildir and
  starts a run when the daemon is idle; the reply comes back to
  `user@hai`. Every conversation is itself a Maildir under `~/.mail`,
  readable in any mail client, searchable with hml, and survives a
  daemon restart. Child agents get their own addresses and report
  back the same way.
- **Voice.** `hai talk` on a key: hstt records and transcribes
  locally, hai answers through piper. Nothing leaves the machine
  unless the model does.
- **Your model, your machine.** hai speaks to any chat-completions
  endpoint with tool calling: llama.cpp, Ollama, vLLM on localhost,
  or a hosted API. The OS stays out of the way: the desktop below
  takes a few hundred megabytes, so on an ordinary laptop nearly all
  the RAM is left for the model (mesa and the Vulkan loader are on the
  ISO; add the Vulkan driver for your GPU from the Void repositories).
  Point `~/.config/hackable/hai.conf` at it:

  ```ini
  url = http://localhost:11434/v1
  model = qwen3:8b
  ```

## Light

Measured on the ISO under qemu (4 GB, no tuning):

| | |
|---|---|
| RAM at the console, after boot | ~300 MB |
| RAM with X, hwm, htray, hnd, hbg and haid up | under 400 MB |
| Processes after boot, kernel threads included | ~105 |
| hsmd (pid 1) | 1.6 MB resident, a 37 KB static binary |
| hwm / hnd / htray / haid | 6 / 8 / 14 / 5 MB resident |

The rest of the numbers are of the same kind. The initramfs init is
583 lines of C, statically linked, no libraries; the boot script is
80 lines of sh, the shutdown script 25, the installer 139. The 1.3 GB
ISO is mostly the kernel's firmware (all of it, so it boots on
anything), the toolchain and the headers; the tools themselves and
their sources are a rounding error.

## On a laptop or a desktop

The ISO is a complete desktop for real hardware, not a demo:

- **Network.** NetworkManager with wpa_supplicant; `nmcli` works as
  the user, no polkit needed. All of linux-firmware is on the ISO, so
  wifi, ethernet and graphics come up on any machine.
- **Sound.** pipewire with wireplumber and the pulse shim, started by
  hwm; volume and mic-mute keys go through `wpctl`, alsamixer is there
  for the rest. sof-firmware for modern laptops' audio.
- **Bluetooth.** bluetoothd runs, `bluetoothctl` pairs as the user.
- **Laptop keys and lid.** acpid: lid close and the sleep button
  suspend through `zzz`, the power button powers off, brightness keys
  step the backlight (brightnessctl, which hwm's own bindings use too).
  htray shows the battery.
- **Input and display.** libinput for touchpads, the kernel's
  modesetting driver for Intel, AMD and nouveau, `xrandr` for external
  monitors; hbg paints each of them.
- **Clock.** chronyd keeps time; the RTC and timezone are read at boot
  from `rc.conf`.
- **Screen lock.** xss-lock and slock after ten idle minutes.

## Made from the kernel up

- **Boot.** grub (BIOS and EFI, hybrid MBR so `dd` to a stick works)
  loads Void's kernel and hos's initramfs. The init in `init/` mounts
  the pseudo filesystems, then does what udev's coldplug does: matches
  every device's modalias against the kernel's alias table and loads
  the drivers the hardware asks for, until a block device carries the
  ISO by label (or the `root=` filesystem of an installed system). It
  mounts the squashfs under a tmpfs overlay, switches root and execs
  `hsmd`. No shell, no udev, no libraries in there; `hos.debug` on the
  command line logs every device and module.
- **The initramfs** is made by `hos-mkinitramfs`: the init plus the
  block, bus and filesystem modules, closed over `modules.dep`. The
  same script runs from `/etc/kernel.d` on an installed system, so a
  kernel update from the Void repositories rebuilds it without dracut.
- **hsmd is pid 1.** It runs `/etc/hsm/boot` (filesystems, modules,
  udev coldplug, keymap, clock, fsck and fstab on a disk root, swap,
  hostname, sysctl), supervises `/var/service` in runit's layout (so
  `sv` and Void's own service directories work unchanged), and on
  `poweroff`, `reboot`, ctrl-alt-del or a signal stops everything,
  runs `/etc/hsm/shutdown` and calls reboot(2). Service logs are under
  `/var/log/hsm/NAME/`.
- **Two gettys, eight services.** `agetty-tty1` (autologin on the
  live system), `agetty-tty2`, udevd, dbus, NetworkManager, acpid,
  bluetoothd and chronyd. That is the whole `SERVICES` file. The lid
  and the sleep button suspend through hos's own `zzz` (hooks in
  `/etc/zzz.d`), the power button powers off; NetworkManager runs
  without polkit, so `nmcli` works for any local user.
- **The session.** tty1 autologin runs `startx` from a profile script;
  `.xinitrc` execs hwm, whose autostart list brings up hbg, htray,
  hnd, screen locking, the keyboard layout, pipewire and haid.

## Packages

hos is described by four text files and a directory, and everything
on it is an xbps package.

- **`PACKAGES`** is the whole package list, base included: hos picks
  its own base (coreutils, util-linux, eudev, kmod, shadow, sudo,
  xbps...) instead of Void's `base-system`, which insists on
  runit-void and a vi. Then the kernel with all firmware, xorg-minimal,
  dbus, NetworkManager, zsh, the runtime libraries of the tools, and
  gcc, make, cmake, git plus every `-devel` header needed to rebuild
  every tool on the running system. About 530 packages in total.
- **`IGNORE`** is xbps's ignorepkg list, in effect on the ISO and on
  installed systems: dracut (linux-base wants it; hos-mkinitramfs
  replaces it) and dependency-chain fat nothing on the ISO links
  against (an OpenCL stack, python through a doc generator, perl
  through git). Only things no shipped binary links to may go there:
  xbps refuses to install with an unresolvable shared library.
- **`SERVICES`** is the list of `/var/service` links. **`overlay/`**
  is copied verbatim over the rootfs: the boot and shutdown scripts,
  the getty service directories, `halt`/`reboot`/`shutdown`,
  hos-mkinitramfs and its kernel hooks, hos-install, os-release and
  issue, `/etc/default/grub`, the system-wide zsh and tmux
  configuration, `/etc/skel`.
- **The tools are packages too.** `mkpkg` builds each sibling
  repository in its tree, lays it out under a package root
  (`/usr/bin`, hai's skills and tools in `/usr/share/hai`, hed's man
  pages, hnd's D-Bus activation file) and runs `xbps-create` on it.
  The version comes from `git describe`, the run dependencies are
  computed from every ELF's `NEEDED` sonames looked up in the rootfs,
  so an unowned library is a build error rather than a broken package.
  No xbps-src, no templates. `hackable-fonts` packages the Iosevka Nerd
  Font the tools name in their `config.h`.
- **A signed repository.** CI builds the packages at every release,
  signs them, and publishes the repository to
  https://42dotmk.github.io/hos; its key is `hos-repo.pub` in this
  tree. The ISO carries that repository in `/etc/xbps.d` and trusts the
  key, so `xbps-install -Su` updates the hackable tools together with
  the rest of the system, on the live ISO, on an installed hos, or on
  plain Void Linux:

  ```sh
  echo repository=https://42dotmk.github.io/hos | sudo tee /etc/xbps.d/10-hos-repository.conf
  sudo xbps-install -S hed hterm hwm hai
  ```

- **Sources next to the packages.** Each tool's working tree is at
  `/usr/src/hackable/<tool>` (hos's own too, so the ISO carries its
  recipe). `make` there, then `make install`, symlinks the result into
  `~/.local/bin`, ahead of the package on `PATH`; the package stays as
  the fallback.

## Build the ISO

```sh
make            # hos-<version>-x86_64.iso, no sudo
make qemu       # boot the newest ISO under kvm
make vmtest     # boot it headless: hsmd as pid 1, services, sv, reboot, poweroff
```

The chain is `rootfs` (xbps installs `PACKAGES` into `build/rootfs`)
→ `packages` (the tools into `build/repo`) → `stage` (overlay,
packages, sources, fonts, the live user, services) → `initramfs` →
`iso` (squashfs plus grub-mkrescue). Each is a make target; `make
stage` is the one to rerun after editing a tool or `overlay/`.

Nothing runs as root: the steps that need it run in a user namespace
(`unshare --map-auto`, so your user needs a line in `/etc/subuid`).
Needs a Void host with xbps, rsync, cpio, zstd, squashfs-tools, grub,
grub-x86_64-efi, xorriso, mtools, python3, and the tools' build
dependencies. The package cache lives in `build/`, so a rebuild only
downloads what changed. `VERSION=`, `REPO=` and `PROJECTS=` are the
knobs; `make sign KEY=...` signs the repository (CI does, with the
private half of `hos-repo.pub`).

## On the live system

- hostname `hos`; user `hos` (password `hos`, passwordless sudo) is
  logged in on tty1 and X starts by itself; root is `root:hos`.
- `hai` in any terminal, `hai talk` on a key. Set `url` and `model`
  in `~/.config/hackable/hai.conf` first (`haid --check` prints what
  it will use). hstt ships without a whisper model and without whisper.cpp's
  build directory; `make model` and `make` in
  `/usr/src/hackable/hstt` fetch and build them.
- The boot menu has entries for no kernel modesetting, a serial
  console, and an init that logs every module and device it touches.

## Install to disk

```sh
sudo hos-install [-u USER] [-H HOSTNAME] /dev/sdX
```

Wipes the disk (it asks you to type the device name), makes a root
filesystem (and an EFI system partition when booted from EFI), copies
the live root onto it as-is with the packages, `/usr/src/hackable`
and the enabled services, writes fstab by UUID, removes the live
user's autologin and sudo, creates USER in the same groups, asks for
both passwords, builds the initramfs and installs grub with
`init=/usr/bin/hsmd`. The installed system boots the same init and the
same pid 1 as the live one. ~130 lines of sh, no menus; keymap,
timezone and wifi are yours afterwards (`rc.conf`, `/etc/localtime`,
`nmcli`).

## Layout

| | |
|---|---|
| `PACKAGES`, `SERVICES`, `IGNORE` | what the rootfs is |
| `overlay/` | copied verbatim into it |
| `init/` | the initramfs init: `init.c` and a `config.h` |
| `mkrootfs`, `mkpkg`, `mkiso` | the steps the Makefile drives |
| `overlay/usr/bin/hos-mkinitramfs`, `hos-install` | shipped, and used by the build |
| `fonts/`, `backgrounds/` | the `hackable-fonts` package and the skel backgrounds |
| `hos-repo.pub` | the package repository's key |
| `vmtest.py` | the headless boot check |
| `pages/` | the front page of the package repository |
