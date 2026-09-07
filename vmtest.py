#!/usr/bin/env python3
"""Boot the newest hos ISO under qemu and drive it over the serial console,
with a freshly built hsmd and the init-related overlay files injected: hos's
init copies anything under /updates in the initramfs onto the live root
before switching to it, so no ISO rebuild is needed to try a change to hsm
or to overlay/etc/hsm.

    python3 vmtest.py pid1     # services up, sv check, restart, logs, poweroff
    python3 vmtest.py reboot   # same, plus a reboot cycle before the poweroff

sv is runit's own binary: hsmd speaks runit's supervise/ protocol, so
`sv check` exercises that; poweroff/reboot are hos's `hsm` wrappers.
Needs qemu-system-x86_64 with /dev/kvm, isoinfo (cdrtools), zstd and cc.  Kernel,
initrd and the console log land in build/vm/."""
import glob, os, re, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
VM = f"{HERE}/build/vm"
HSM = f"{HERE}/../hsm"
OVERLAY = f"{HERE}/overlay"
# what the ISO's grub menu passes, minus console=
BASEARGS = "hos.live=HOS init=/usr/bin/hsmd loglevel=4"
INJECT = ["etc/hsm/boot", "etc/hsm/shutdown"]


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

    add("/usr/src/hackable/hsm/hsmd", f"{VM}/hsmd")
    add("/usr/src/hackable/hsm/hsm", f"{VM}/hsm")
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
        rx, end = re.compile(pat.encode()), time.time() + timeout
        while time.time() < end:
            m = rx.search(self.buf)
            if m:
                out, self.buf = self.buf[:m.start()], self.buf[m.end():]
                return out.decode(errors="replace")
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


class Machine:
    def __init__(self, iso, tag):
        args = BASEARGS + " console=ttyS0,115200"
        sock = f"/run/user/{os.getuid()}/hos-vmtest-{tag}.sock"  # unix paths: < 108 bytes
        if os.path.exists(sock):
            os.unlink(sock)
        self.q = subprocess.Popen(
            ["qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-smp", "4", "-m", "4G",
             "-cdrom", iso, "-kernel", f"{VM}/vmlinuz", "-initrd", initrd(tag), "-append", args,
             "-display", "none", "-chardev", f"socket,id=s0,path={sock},server=on,wait=off",
             "-serial", "chardev:s0"], stdout=open(f"{VM}/qemu.{tag}.log", "wb"),
            stderr=subprocess.STDOUT)
        self.ser = Serial(sock, f"{VM}/console.{tag}.log")

    def shell(self):
        """wait for agetty's autologin, then give bash a prompt we can find"""
        self.ser.expect(r"automatic login", 300)
        end = time.time() + 60
        while time.time() < end:
            self.ser.send("\nPS1='HOS''P> '\n")  # the echo must not match the prompt
            try:
                self.ser.expect(r"HOSP> ", 3)
                return
            except TimeoutError:
                pass
        raise TimeoutError("no shell")

    def run(self, cmd, timeout=60):
        self.ser.buf = b""
        self.ser.send(cmd + "\n")
        out = self.ser.expect(r"HOSP> ", timeout)
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


def scenario_pid1(iso, m=None):
    m = m or Machine(iso, "pid1")
    m.shell()
    ok = check("hsmd" in m.run("cat /proc/1/comm"), "hsmd is pid 1")
    st = m.run("hsm status")
    ok &= check(all(re.search(rf"^{s}\s+run", st, re.M) for s in ("dbus", "NetworkManager", "udevd", "agetty-tty1")),
                "dbus, NetworkManager, udevd, agetty-tty1 run")
    ok &= check(m.run("sv check dbus; echo rc=$?").strip().endswith("rc=0"), "sv check dbus")
    ok &= check("dbus" in m.run("ls /var/log/hsm"), "logs under /var/log/hsm")
    ok &= check(re.search(r"dbus\s+run", m.run("hsm restart dbus; sleep 2; hsm status | grep dbus")),
                "hsm restart dbus")
    m.down("poweroff", r"hsmd: poweroff")
    return ok


def scenario_reboot(iso):
    m = Machine(iso, "reboot")
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


if __name__ == "__main__":
    scenarios = {"pid1": scenario_pid1, "reboot": scenario_reboot}
    if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
        sys.exit(f"usage: vmtest.py {'|'.join(scenarios)}")
    sys.exit(0 if scenarios[sys.argv[1]](prepare()) else 1)
