#!/usr/bin/env python3
"""Boot the newest hos ISO under qemu and drive it over the serial console,
with a freshly built hsmd and the init-related overlay files injected: hos's
init copies anything under /updates in the initramfs onto the live root
before switching to it, so no ISO rebuild is needed to try a change to hsm
or to overlay/etc/hsm.

    python3 vmtest.py pid1     # services up, sv check, restart, logs, the
                               # live autologin into X, poweroff
    python3 vmtest.py reboot   # same, plus a reboot cycle before the poweroff
    python3 vmtest.py install  # hos-install onto a scratch disk under BIOS
                               # and under EFI (OVMF), then boot each disk
                               # through its own grub: ext4 root, services,
                               # xdm instead of the autologin, the new user
                               # logs in at the greeter (typed through
                               # qemu's keyboard) and hwm runs
    python3 vmtest.py keep     # hos-install next to partitions it must not
                               # touch: into one partition picked at its
                               # prompt (BIOS), and into a disk's free space
                               # beside an existing ESP (EFI), and
                               # into a partition of a disk with no ESP
                               # (EFI: hos makes one), and over an ESP
                               # formatted when asked (EFI); their files
                               # survive and the disk boots as above

sv is runit's own binary: hsmd speaks runit's supervise/ protocol, so
`sv check` exercises that; poweroff/reboot are hos's `hsm` wrappers. The
installed disks get a root getty and console=ttyS0 added after hos-install
is done (the test has no other way in); everything else is as hos-install
left it. Needs qemu-system-x86_64 with /dev/kvm, isoinfo (cdrtools), zstd,
cc, and OVMF for the EFI half. Kernel, initrd, console logs and screenshots
of the greeter and the session land in build/vm/."""
import atexit, glob, os, re, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
VM = f"{HERE}/build/vm"
HSM = f"{HERE}/../hsm"
OVERLAY = f"{HERE}/overlay"
OVMF = os.environ.get("OVMF", "/usr/share/qemu/edk2-x86_64-code.fd")
# the NVRAM template; each EFI disk gets its own copy, so boot entries
# grub-install makes survive into the disk's own boot, as on hardware
OVMF_VARS = os.environ.get("OVMF_VARS", "/usr/share/qemu/edk2-i386-vars.fd")
# what the ISO's grub menu passes, minus console=
BASEARGS = "hos.live=HOS init=/usr/bin/hsmd loglevel=4"
INJECT = ["etc/hsm/boot", "etc/hsm/shutdown", "usr/bin/hos-install"]
PASSWORD = "vmtest"


def sh(*cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def prepare():
    iso = max(glob.glob(f"{HERE}/hos-*.iso"), key=os.path.getmtime)
    os.makedirs(VM, exist_ok=True)
    for f in ("vmlinuz", "initramfs"):
        if not os.path.exists(f"{VM}/{f}") or os.path.getmtime(f"{VM}/{f}") < os.path.getmtime(iso):
            with open(f"{VM}/{f}", "wb") as o:
                sh("isoinfo", "-R", "-x", f"/boot/{f}", "-i", iso, stdout=o, stderr=subprocess.DEVNULL)
    cflags = ["-std=c11", "-pedantic", "-Wall", "-Wextra", "-Os", "-D_GNU_SOURCE", "-static",
              "-DHSM_VERSION=\"vmtest\""]  # static: the ISO's glibc may differ from the host's
    sh("cc", *cflags, "-o", f"{VM}/hsmd", f"{HSM}/hsmd.c", f"{HSM}/log.c")
    sh("cc", *cflags, "-o", f"{VM}/hsm", f"{HSM}/hsm.c")
    return iso


def cpio_newc(entries):
    """entries: (path, mode, data, symlink-target-or-None); everything root-owned"""
    out = bytearray()
    ino = 1

    def rec(path, mode, data):
        nonlocal ino
        name = path.encode() + b"\0"
        out.extend(b"070701" + b"".join(b"%08X" % v for v in (
            ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0)) + name)
        while len(out) % 4:
            out.append(0)
        out.extend(data)
        while len(out) % 4:
            out.append(0)
        ino += 1

    dirs = set()
    for path, mode, data, link in entries:
        d, parts = os.path.dirname(path), []
        while d and d not in dirs:
            parts.append(d)
            d = os.path.dirname(d)
        for d in reversed(parts):
            dirs.add(d)
            rec(d, 0o040755, b"")
        if link is not None:
            rec(path, 0o120777, link.encode())
        else:
            rec(path, 0o100000 | mode, data)
    rec("TRAILER!!!", 0, b"")
    return bytes(out)


def initrd(tag):
    """the ISO's initramfs with an /updates cpio appended inside the same
    zstd stream (the kernel unpacks concatenated cpio archives, but not an
    uncompressed one after a zstd one); hos's init copies /updates over
    the new root"""
    e = []

    def add(dst, src, mode=0o755):
        e.append((f"updates{dst}", mode, open(src, "rb").read(), None))

    # over the packaged ones (the hsm package puts them in /usr/bin)
    add("/usr/bin/hsmd", f"{VM}/hsmd")
    add("/usr/bin/hsm", f"{VM}/hsm")
    for p in INJECT:
        add("/" + p, f"{OVERLAY}/{p}", os.stat(f"{OVERLAY}/{p}").st_mode & 0o777)
    # a getty on the serial console, logging root in without a password
    e.append(("updates/var/service/agetty-ttyS0", 0, None, "/etc/sv/agetty-ttyS0"))
    e.append(("updates/etc/sv/agetty-ttyS0/conf", 0o644,
              b'GETTY_ARGS="-L -8 -a root --noclear"\nBAUD_RATE=115200\nTERM_NAME=vt100\n', None))
    path = f"{VM}/initramfs.{tag}"
    raw = subprocess.run(["zstd", "-dc", f"{VM}/initramfs"], check=True, capture_output=True).stdout
    with open(path, "wb") as o:
        subprocess.run(["zstd", "-q", "-3"], input=raw + cpio_newc(e), stdout=o, check=True)
    return path


class Serial:
    def __init__(self, path, log):
        self.log = open(log, "wb")
        self.buf = b""
        for _ in range(100):
            try:
                self.s = socket.socket(socket.AF_UNIX)
                self.s.connect(path)
                break
            except OSError:
                time.sleep(0.1)
        self.s.settimeout(0.2)

    def expect(self, pat, timeout):
        """wait for pat; returns (text before it, the match)"""
        rx, end = re.compile(pat.encode()), time.time() + timeout
        while time.time() < end:
            m = rx.search(self.buf)
            if m:
                out, self.buf = self.buf[:m.start()], self.buf[m.end():]
                return out.decode(errors="replace"), m
            try:
                d = self.s.recv(65536)
                if d:
                    self.buf += d
                    self.log.write(d)
                    self.log.flush()
            except (socket.timeout, OSError):
                pass
        raise TimeoutError(f"waiting for {pat!r}; last output: {self.buf[-800:]!r}")

    def send(self, s):
        self.s.sendall(s.encode())


class Monitor:
    """qemu's human monitor on a unix socket: screendump and sendkey. (Not
    QMP: qemu 11 sets up an io_uring for a -qmp socket, which dies under a
    small RLIMIT_MEMLOCK; the HMP one needs none.)"""

    def __init__(self, path):
        for _ in range(100):
            try:
                self.s = socket.socket(socket.AF_UNIX)
                self.s.connect(path)
                break
            except OSError:
                self.s.close()
                time.sleep(0.1)
        else:
            raise SystemExit(f"no qemu monitor at {path}")
        self.s.settimeout(30)
        self.prompt()

    def prompt(self):
        buf = b""
        while not buf.endswith(b"(qemu) "):
            d = self.s.recv(4096)
            if not d:
                raise SystemExit("qemu monitor closed")
            buf += d
        return buf

    def cmd(self, line):
        self.s.sendall(line.encode() + b"\n")
        return self.prompt()

    def screenshot(self, path):
        self.cmd(f"screendump {path} -f png")

    def type(self, text):
        keys = {"\n": "ret", " ": "spc", "-": "minus", ".": "dot", "/": "slash"}
        for ch in text:
            k = keys.get(ch, ch)
            if ch.isupper():
                k = f"shift-{ch.lower()}"
            self.cmd(f"sendkey {k}")
            time.sleep(0.05)


class Machine:
    """iso: the live medium; disk: a raw image on virtio; efi: OVMF (as a
    read-only pflash drive - qemu refuses a code-only image as -bios);
    kernel: boot the ISO's kernel and the /updates initrd directly (the
    live system), else the disk's own grub boots"""

    def __init__(self, tag, iso=None, disk=None, efi=False, kernel=True):
        self.tag = tag
        run = f"/run/user/{os.getuid()}"  # unix paths: < 108 bytes
        sock, msock = f"{run}/hos-vmtest-{tag}.sock", f"{run}/hos-vmtest-{tag}.mon"
        for s in (sock, msock):
            if os.path.exists(s):
                os.unlink(s)
        cmd = ["qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-smp", "4", "-m", "4G",
               "-device", "virtio-vga,xres=1280,yres=800", "-display", "none",
               "-chardev", f"socket,id=s0,path={sock},server=on,wait=off", "-serial", "chardev:s0",
               "-monitor", f"unix:{msock},server=on,wait=off"]
        if efi:
            cmd += ["-drive", f"if=pflash,format=raw,readonly=on,file={OVMF}"]
            if disk:
                if not os.path.exists(f"{disk}.vars"):
                    sh("cp", OVMF_VARS, f"{disk}.vars")
                cmd += ["-drive", f"if=pflash,format=raw,file={disk}.vars"]
        if iso:
            # on AHCI, as real machines have it: with OVMF keeping NVRAM,
            # the default PIIX PATA cd never answers Linux's probe
            cmd += ["-device", "ahci,id=ahci",
                    "-drive", f"file={iso},media=cdrom,if=none,id=cd,readonly=on",
                    "-device", "ide-cd,drive=cd,bus=ahci.0"]
        if disk:
            cmd += ["-drive", f"file={disk},if=virtio,format=raw"]
        if kernel:
            cmd += ["-kernel", f"{VM}/vmlinuz", "-initrd", initrd(tag),
                    "-append", BASEARGS + " console=ttyS0,115200"]
        self.q = subprocess.Popen(cmd, stdout=open(f"{VM}/qemu.{tag}.log", "wb"),
                                  stderr=subprocess.STDOUT)
        # a failed check or a timeout must not leave the VM running
        atexit.register(lambda q=self.q: q.poll() is None and q.kill())
        self.ser = Serial(sock, f"{VM}/console.{tag}.log")
        self.mon = Monitor(msock)

    def shell(self):
        """wait for agetty's autologin, then give the shell a prompt we can find"""
        # agetty's line can come interleaved with hsmd's, so the root
        # shell's own prompt counts too
        self.ser.expect(r"automatic login|-bash-[0-9.]+# ", 300)
        end = time.time() + 60
        while time.time() < end:
            self.ser.send("\nPS1='HOS''P> '\n")  # the echo must not match the prompt
            try:
                self.ser.expect(r"HOSP> ", 3)
                self.ser.buf = b""
                return
            except TimeoutError:
                pass
        raise TimeoutError("no shell")

    def run(self, cmd, timeout=60):
        self.ser.buf = b""
        self.ser.send(cmd + "\n")
        out, _ = self.ser.expect(r"HOSP> ", timeout)
        out = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out.split("\n", 1)[1] if "\n" in out else "")
        out = out.replace("\r", "")  # the bracketed-paste escape leaves one before the first line
        print(f"$ {cmd}\n{out.strip()}\n", flush=True)
        return out

    def down(self, cmd, marker):
        """send a shutdown command, wait for hsmd's marker line, then for qemu to exit"""
        print(f"--- {cmd}", flush=True)
        self.ser.buf = b""
        self.ser.send(cmd + "\n")
        self.ser.expect(marker, 120)
        try:
            self.q.wait(timeout=120)
        except subprocess.TimeoutExpired:
            self.q.kill()
            raise SystemExit("qemu still running after " + cmd)
        print("qemu exited", self.q.returncode, flush=True)


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    return bool(cond)


def waitfor(m, cmd, want, tries=30):
    """rerun cmd until its output contains want (services and X take a while)"""
    out = ""
    for _ in range(tries):
        out = m.run(cmd)
        if want in out:
            break
        time.sleep(2)
    return out


def session(m, user):
    """what an X session of user looks like: hwm, its autostart, and (under
    xdm) the environment pam_rundir and Xsession give it"""
    ok = check("hwm" in waitfor(m, f"pgrep -u {user} -l hwm", "hwm"), f"hwm runs as {user}")
    time.sleep(8)
    m.mon.screenshot(f"{VM}/session.{m.tag}.png")
    ok &= check("htray" in m.run(f"pgrep -u {user} -l htray; pgrep -u {user} -l hnd"),
                "hwm's autostart ran (htray)")
    return ok


def scenario_pid1(iso, m=None):
    m = m or Machine("pid1", iso=iso)
    m.shell()
    ok = check("hsmd" in m.run("cat /proc/1/comm"), "hsmd is pid 1")
    st = m.run("hsm status")
    ok &= check(all(re.search(rf"^{s}\s+run", st, re.M) for s in ("dbus", "NetworkManager", "udevd", "agetty-tty1")),
                "dbus, NetworkManager, udevd, agetty-tty1 run")
    ok &= check(m.run("sv check dbus; echo rc=$?").strip().endswith("rc=0"), "sv check dbus")
    ok &= check("dbus" in m.run("ls /var/log/hsm"), "logs under /var/log/hsm")
    ok &= check(re.search(r"dbus\s+run", m.run("hsm restart dbus; sleep 2; hsm status | grep dbus")),
                "hsm restart dbus")
    # the live session is the autologin on tty1 and startx, not xdm
    ok &= check(not re.search(r"^xdm\s", m.run("hsm status"), re.M), "xdm not enabled on the live system")
    ok &= session(m, "hos")
    m.down("poweroff", r"hsmd: poweroff")
    return ok


def scenario_reboot(iso):
    m = Machine("reboot", iso=iso)
    m.shell()
    ok = check("hsmd" in m.run("cat /proc/1/comm"), "hsmd is pid 1")
    print("--- reboot", flush=True)
    m.ser.buf = b""
    m.ser.send("reboot\n")
    m.ser.expect(r"hsmd: reboot", 120)
    m.ser.expect(r"hsmd: supervising", 300)
    m.shell()
    ok &= check("0 min" in m.run("uptime"), "came back after reboot")
    ok &= check(re.search(r"dbus\s+run", m.run("hsm status")), "services up after reboot")
    m.down("poweroff", r"hsmd: poweroff")
    return ok


def install(iso, efi, prep=None, argv="/dev/vda", pick=None, root=None, keep=(), shared_esp=False, tag=None,
            esp_format="n"):
    """hos-install onto a scratch disk, then boot it. prep: shell run on the
    live system first (partitions to keep); argv: hos-install's target
    arguments, or with pick the answer to its own prompt; root: the
    partition hos lands on; keep: shell checks, each printing "kept", run
    on the installed system for what must have survived; shared_esp: the
    ESP was there before hos with another system's fallback loader, which
    must stay as it was (hos then boots by its NVRAM entry); esp_format:
    the answer when hos-install offers to format an existing ESP"""
    tag = ("efi" if efi else "bios") + (f"-{tag}" if tag else "")
    disk = f"{VM}/disk.{tag}.img"
    for f in (disk, f"{disk}.vars"):
        if os.path.exists(f):
            os.unlink(f)
    sh("truncate", "-s", "24G", disk)
    m = Machine(f"install-{tag}", iso=iso, disk=disk, efi=efi)
    m.shell()
    ok = check(("efi" if efi else "none") in m.run("[ -d /sys/firmware/efi ] && echo efi || echo none"),
               f"booted {'EFI' if efi else 'BIOS'}")
    if prep:
        m.run(prep, 120)
    print(f"--- hos-install ({tag})", flush=True)
    m.ser.buf = b""
    m.ser.send(f"hos-install -u tester -H hostest {argv}\n")
    if pick:
        m.ser.expect(r"largest free space\): ", 60)
        m.ser.send(pick + "\n")
    _, hit = m.ser.expect(r"Type (\S+) to continue: |\nhos-install: [^\n]*", 60)
    if not hit.group(1):
        raise SystemExit(f"hos-install failed: {hit.group(0).decode().strip()}")
    m.ser.send(hit.group(1).decode() + "\n")
    while True:
        out, hit = m.ser.expect(r"(password: ?|again: ?|\[y/N\] |== done[^\n]*|\nhos-install: [^\n]*|HOSP> )", 900)
        what = hit.group(0).decode()
        if what.startswith(("password", "again")):
            m.ser.send(PASSWORD + "\n")
        elif what.startswith("[y/N]"):
            m.ser.send(esp_format + "\n")
        elif "== done" in what:
            # the phase times hos-install prints before its last line
            for line in out.replace("\r", "").splitlines():
                if re.match(r"^  \S.*\d+\.\ds$", line):
                    print(line, flush=True)
            print(what.strip(), flush=True)
            break
        else:
            raise SystemExit(f"hos-install failed: {what.strip()}")
    m.ser.expect(r"HOSP> ", 60)
    root = root or ("/dev/vda2" if efi else "/dev/vda1")
    # the test's way in: a root autologin on ttyS0 (hos-install copied the
    # live root, the injected getty included) and a serial console
    m.run(f"mount {root} /mnt && ln -sfn /etc/sv/agetty-ttyS0 /mnt/var/service/agetty-ttyS0 && "
          "printf 'GETTY_ARGS=\"-L -8 -a root --noclear\"\\nBAUD_RATE=115200\\nTERM_NAME=vt100\\n' "
          "> /mnt/etc/sv/agetty-ttyS0/conf && "
          "sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=\"/&console=tty0 console=ttyS0,115200 /' /mnt/etc/default/grub && "
          "for d in dev proc sys; do mount --rbind /$d /mnt/$d; done && "
          "chroot /mnt grub-mkconfig -o /boot/grub/grub.cfg 2>&1 | tail -2; "
          "grep -m1 -E '^\\s+linux' /mnt/boot/grub/grub.cfg; umount -R /mnt", 120)
    m.down("poweroff", r"hsmd: poweroff")

    m = Machine(f"disk-{tag}", disk=disk, efi=efi, kernel=False)
    m.shell()
    ok &= check(re.search(rf"^{root} ext4", m.run("findmnt -no SOURCE,FSTYPE /"), re.M), f"root is ext4 on {root}")
    for k in keep:
        ok &= check("kept" in m.run(k), f"kept: {k}")
    ok &= check("hostest" in m.run("cat /proc/sys/kernel/hostname"), "hostname from -H")
    ok &= check("init=/usr/bin/hsmd" in m.run("cat /proc/cmdline"), "grub passed init=/usr/bin/hsmd")
    ok &= check("hos" not in m.run("getent passwd hos; ls /etc/sudoers.d"), "live user gone")
    ok &= check("-a " not in m.run("cat /etc/sv/agetty-tty1/conf; ls /etc/profile.d"),
                "no tty1 autologin")
    ok &= check("startx" not in m.run("ls /etc/profile.d"), "no startx from tty1")
    if efi and not shared_esp:
        ok &= check("BOOTX64.EFI" in m.run("ls /boot/efi/EFI/BOOT"), "removable EFI path")
    if efi and shared_esp:
        ok &= check("kept" in m.run("grep -q hos-vmtest /boot/efi/EFI/BOOT/BOOTX64.EFI && echo kept"),
                    "shared ESP: the other system's fallback loader untouched")
    st = waitfor(m, "hsm status", "xdm")
    for s in ("udevd", "dbus", "NetworkManager", "xdm", "agetty-tty1"):
        ok &= check(re.search(rf"^{s}\s+run", st, re.M), f"{s} runs")
    ok &= check("Xorg" in waitfor(m, "pgrep -l Xorg", "Xorg"), "Xorg runs under xdm")
    time.sleep(12)  # the greeter maps a while after X is up
    m.mon.screenshot(f"{VM}/greeter.{m.tag}.png")
    m.mon.type("tester\n")
    # keys typed before PAM's password prompt is up are lost: wait, and
    # type it again while nobody is logged in (the greeter keeps the name)
    for _ in range(3):
        time.sleep(4)
        m.mon.type(f"{PASSWORD}\n")
        if "hwm" in waitfor(m, "pgrep -u tester -l hwm", "hwm", tries=10):
            break
    ok &= check("hwm" in m.run("pgrep -u tester -l hwm"), "tester logged in at xdm")
    env = m.run("tr '\\0' '\\n' < /proc/$(pgrep -u tester -x hwm | head -1)/environ | "
                "grep -E '^(XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS|LANG)='")
    ok &= check("XDG_RUNTIME_DIR=/run/user/" in env, "session has XDG_RUNTIME_DIR (pam_rundir)")
    ok &= check("DBUS_SESSION_BUS_ADDRESS=" in env, "session has a session bus")
    ok &= check("LANG=en_US.UTF-8" in env, "session has the locale")
    ok &= session(m, "tester")
    # the greeter's hbg (root, the 42 picture) gave way to the user's own
    ok &= check("hbg" in m.run("pgrep -u tester -l hbg") and
                "hbg" not in m.run("pgrep -u root -l hbg"), "the user's hbg replaced the greeter's")
    m.down("poweroff", r"hsmd: poweroff")
    return ok


def scenario_install(iso):
    ok = install(iso, efi=False)
    if os.path.exists(OVMF):
        ok &= install(iso, efi=True)
    else:
        print(f"skip EFI: no {OVMF}")
    return ok


MARK = "echo hos-vmtest > /mnt/marker && umount /mnt"
KEPT = "mount -o ro {0} /mnt && grep -q hos-vmtest /mnt/marker && echo kept; umount /mnt"


def scenario_keep(iso):
    # BIOS: a disk of files and an empty partition, that one picked at the prompt
    ok = install(iso, efi=False, tag="part", argv="", pick="/dev/vda2", root="/dev/vda2",
                 prep="printf 'label: dos\\nsize=2G, type=83\\nsize=10G, type=83\\n' | sfdisk -q /dev/vda && "
                      "udevadm settle; mkfs.ext4 -q /dev/vda1 && mount /dev/vda1 /mnt && " + MARK,
                 keep=[KEPT.format("/dev/vda1")])
    if not os.path.exists(OVMF):
        print(f"skip EFI: no {OVMF}")
        return ok
    # EFI, the same disk of files with no ESP: hos makes one in the free space
    ok &= install(iso, efi=True, tag="noesp", argv="/dev/vda2", root="/dev/vda2",
                  prep="printf 'label: gpt\\nsize=2G, type=linux\\nsize=10G, type=linux\\n' | sfdisk -q /dev/vda && "
                       "udevadm settle; mkfs.ext4 -q /dev/vda1 && mount /dev/vda1 /mnt && " + MARK,
                  keep=[KEPT.format("/dev/vda1"),
                        "findmnt -no SOURCE /boot/efi | grep -qx /dev/vda3 && echo kept"])
    # EFI: someone's ESP and a data partition, hos into the free space after them
    ok &= install(iso, efi=True, tag="free", argv="-f /dev/vda", root="/dev/vda3", shared_esp=True,
                  prep="printf 'label: gpt\\nsize=512M, type=uefi\\nsize=2G, type=linux\\n' | sfdisk -q /dev/vda && "
                       "udevadm settle; mkfs.vfat -F32 /dev/vda1 >/dev/null && mkfs.ext4 -q /dev/vda2 && "
                       "mount /dev/vda1 /mnt && mkdir -p /mnt/EFI/other /mnt/EFI/BOOT && echo hos-vmtest > /mnt/EFI/other/marker && "
                       "echo hos-vmtest > /mnt/EFI/BOOT/BOOTX64.EFI && "
                       "umount /mnt && mount /dev/vda2 /mnt && " + MARK,
                  keep=[KEPT.format("/dev/vda2"),
                        "grep -q hos-vmtest /boot/efi/EFI/other/marker && echo kept"])
    # EFI: the same, but the ESP formatted when asked - a clean start
    ok &= install(iso, efi=True, tag="clean", argv="-f /dev/vda", root="/dev/vda3", esp_format="y",
                  prep="printf 'label: gpt\\nsize=512M, type=uefi\\nsize=2G, type=linux\\n' | sfdisk -q /dev/vda && "
                       "udevadm settle; mkfs.vfat -F32 /dev/vda1 >/dev/null && mkfs.ext4 -q /dev/vda2 && "
                       "mount /dev/vda1 /mnt && mkdir -p /mnt/EFI/other /mnt/EFI/BOOT && echo hos-vmtest > /mnt/EFI/other/marker && "
                       "echo hos-vmtest > /mnt/EFI/BOOT/BOOTX64.EFI && "
                       "umount /mnt && mount /dev/vda2 /mnt && " + MARK,
                  keep=[KEPT.format("/dev/vda2"),
                        "[ ! -e /boot/efi/EFI/other ] && findmnt -no SOURCE /boot/efi | grep -qx /dev/vda1 && echo kept"])
    return ok


if __name__ == "__main__":
    scenarios = {"pid1": scenario_pid1, "reboot": scenario_reboot, "install": scenario_install,
                 "keep": scenario_keep}
    if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
        sys.exit(f"usage: vmtest.py {'|'.join(scenarios)}")
    sys.exit(0 if scenarios[sys.argv[1]](prepare()) else 1)
