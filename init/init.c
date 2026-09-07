/* hos init - the initramfs' /init.
 *
 * Finds the root the kernel command line asks for - the live medium by its
 * iso9660 label, or a disk by uuid, label or device - loading the block
 * drivers the hardware announces on the way, assembles the live root (the
 * medium's squashfs on a loop device under a tmpfs overlay), copies
 * /updates over it, and switches to init=.  Static and alone: no libkmod
 * (hos-mkinitramfs stores the modules uncompressed, so finit_module is
 * all it takes), no shell, no udev in here.  See config.h. */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <fnmatch.h>
#include <limits.h>
#include <linux/loop.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#include "config.h"

#define LEN(a) (sizeof(a) / sizeof((a)[0]))

struct mod {
    char name[64]; /* file name without .ko*, '-' as '_' */
    char *path;    /* as in modules.dep: relative to modroot */
    char *deps;    /* the rest of its modules.dep line */
    int loaded;
};

struct alias {
    char *pattern, *name;
};

static struct mod *mods;
static int nmods;
static struct alias *aliases;
static int naliases;
static char modroot[PATH_MAX]; /* moddir/<release> */

/* from the kernel command line */
static const char *live; /* iso label, or NULL for a disk root */
static const char *root; /* UUID=, LABEL= or /dev/... */
static const char *init; /* what to exec in the new root */
static int rw, verbose;

static void msg(const char *fmt, ...) {
    va_list ap;

    dprintf(2, "hos init: ");
    va_start(ap, fmt);
    vdprintf(2, fmt, ap);
    va_end(ap);
    dprintf(2, "\n");
}

static void fail(const char *fmt, ...) {
    va_list ap;

    dprintf(2, "hos init: ");
    va_start(ap, fmt);
    vdprintf(2, fmt, ap);
    va_end(ap);
    dprintf(2, "\nhos init: cannot go on; ctrl-alt-del reboots\n");
    for (;;)
        pause();
}

static void join(char *dst, size_t len, const char *dir, const char *name) {
    if ((size_t)snprintf(dst, len, "%s/%s", dir, name) >= len)
        fail("path too long: %s/%s", dir, name);
}

static char *readfile(const char *path, size_t *len) {
    char *buf;
    size_t cap = 1 << 16, n = 0;
    ssize_t r;
    int fd;

    if ((fd = open(path, O_RDONLY)) < 0)
        return NULL;
    buf = malloc(cap);
    while (buf && (r = read(fd, buf + n, cap - n - 1)) > 0) {
        n += r;
        if (n + 1 >= cap)
            buf = realloc(buf, cap *= 2);
    }
    close(fd);
    if (!buf)
        fail("out of memory reading %s", path);
    buf[n] = 0;
    if (len)
        *len = n;
    return buf;
}

/* "usb-storage" and "usb_storage" are the same module */
static void normalize(char *s) {
    for (; *s; s++)
        if (*s == '-')
            *s = '_';
}

static struct mod *findmod(const char *name) {
    char key[64];
    int i;

    snprintf(key, sizeof(key), "%s", name);
    normalize(key);
    for (i = 0; i < nmods; i++)
        if (!strcmp(mods[i].name, key))
            return &mods[i];
    return NULL;
}

static struct mod *findmodbypath(const char *path) {
    int i;

    for (i = 0; i < nmods; i++)
        if (!strcmp(mods[i].path, path))
            return &mods[i];
    return NULL;
}

/* modules.dep: "path: dep dep..." per line; modules.alias: "alias PATTERN
 * NAME" per line, already filtered to what the initramfs carries */
static void loadtables(void) {
    struct utsname u;
    char path[PATH_MAX], *buf, *line, *next, *p, *base;
    int i;

    uname(&u);
    snprintf(modroot, sizeof(modroot), "%s/%s", moddir, u.release);

    join(path, sizeof(path), modroot, "modules.dep");
    if (!(buf = readfile(path, NULL)))
        fail("%s: %s", path, strerror(errno));
    for (p = buf; *p; p++)
        nmods += *p == '\n';
    mods = calloc(nmods + 1, sizeof(*mods));
    for (i = 0, line = buf; line && *line; line = next) {
        if ((next = strchr(line, '\n')))
            *next++ = 0;
        if (!(p = strchr(line, ':')))
            continue;
        *p++ = 0;
        mods[i].path = line;
        mods[i].deps = p;
        base = strrchr(line, '/');
        base = base ? base + 1 : line;
        snprintf(mods[i].name, sizeof(mods[i].name), "%s", base);
        if ((p = strstr(mods[i].name, ".ko")))
            *p = 0;
        normalize(mods[i].name);
        i++;
    }
    nmods = i;

    join(path, sizeof(path), modroot, "modules.alias");
    if (!(buf = readfile(path, NULL)))
        fail("%s: %s", path, strerror(errno));
    for (p = buf; *p; p++)
        naliases += *p == '\n';
    aliases = calloc(naliases + 1, sizeof(*aliases));
    for (i = 0, line = buf; line && *line; line = next) {
        if ((next = strchr(line, '\n')))
            *next++ = 0;
        if (strncmp(line, "alias ", 6))
            continue;
        aliases[i].pattern = line + 6;
        if (!(p = strchr(aliases[i].pattern, ' ')))
            continue;
        *p++ = 0;
        aliases[i].name = p;
        normalize(p);
        i++;
    }
    naliases = i;
    if (verbose)
        msg("%d modules, %d aliases under %s", nmods, naliases, modroot);
}

static int loadmod(struct mod *m) {
    char path[PATH_MAX], deps[1024], *tok, *save;
    struct mod *d;
    int fd, r;

    if (m->loaded)
        return 0;
    m->loaded = 1;
    snprintf(deps, sizeof(deps), "%s", m->deps);
    for (tok = strtok_r(deps, " ", &save); tok;
         tok = strtok_r(NULL, " ", &save))
        if ((d = findmodbypath(tok)))
            loadmod(d);
    join(path, sizeof(path), modroot, m->path);
    if ((fd = open(path, O_RDONLY)) < 0) {
        msg("%s: %s", path, strerror(errno));
        return -1;
    }
    r = syscall(SYS_finit_module, fd, "", 0);
    close(fd);
    if (r < 0 && errno != EEXIST) {
        msg("%s: %s", m->name, strerror(errno));
        return -1;
    }
    if (verbose)
        msg("loaded %s", m->name);
    return 0;
}

/* what udev's coldplug does: every device on every bus names the driver it
 * wants in its modalias; load the ones we carry. Returns how many were new,
 * since a loaded controller driver makes more devices appear. */
static int coldplug(void) {
    DIR *bus, *devs;
    struct dirent *b, *e;
    struct mod *m;
    char path[PATH_MAX], alias[512];
    int fd, i, n = 0;
    ssize_t r;

    if (!(bus = opendir("/sys/bus")))
        return 0;
    while ((b = readdir(bus))) {
        if (b->d_name[0] == '.')
            continue;
        snprintf(path, sizeof(path), "/sys/bus/%s/devices", b->d_name);
        if (!(devs = opendir(path)))
            continue;
        while ((e = readdir(devs))) {
            if (e->d_name[0] == '.')
                continue;
            snprintf(path, sizeof(path), "/sys/bus/%s/devices/%s/modalias",
                     b->d_name, e->d_name);
            if ((fd = open(path, O_RDONLY)) < 0)
                continue;
            r = read(fd, alias, sizeof(alias) - 1);
            close(fd);
            if (r <= 0)
                continue;
            alias[r] = 0;
            alias[strcspn(alias, "\n")] = 0;
            for (i = 0; i < naliases; i++) {
                if (fnmatch(aliases[i].pattern, alias, 0))
                    continue;
                if ((m = findmod(aliases[i].name)) && !m->loaded) {
                    if (verbose)
                        msg("%s wants %s", alias, m->name);
                    if (loadmod(m) == 0)
                        n++;
                }
            }
        }
        closedir(devs);
    }
    closedir(bus);
    return n;
}

/* iso9660: primary volume descriptor at 32k, volume id space padded */
static int isolabel(int fd, char *label, size_t len) {
    unsigned char b[2048];
    size_t n;

    if (pread(fd, b, sizeof(b), 32768) != (ssize_t)sizeof(b))
        return -1;
    if (b[0] != 1 || memcmp(b + 1, "CD001", 5))
        return -1;
    n = 32;
    while (n > 0 && b[40 + n - 1] == ' ')
        n--;
    if (n >= len)
        n = len - 1;
    memcpy(label, b + 40, n);
    label[n] = 0;
    return 0;
}

/* ext2/3/4: superblock at 1k, magic 0xef53, uuid and label after it */
static int ext4ids(int fd, char *uuid, size_t ulen, char *label, size_t llen) {
    unsigned char b[1024];
    int i;

    if (pread(fd, b, sizeof(b), 1024) != (ssize_t)sizeof(b))
        return -1;
    if (b[56] != 0x53 || b[57] != 0xef)
        return -1;
    for (i = 0; i < 16 && (size_t)(i * 2 + 5) < ulen; i++)
        snprintf(uuid + strlen(uuid), ulen - strlen(uuid),
                 (i == 4 || i == 6 || i == 8 || i == 10) ? "-%02x" : "%02x",
                 b[104 + i]);
    snprintf(label, llen, "%.16s", (char *)b + 120);
    return 0;
}

static int wanted(const char *dev) {
    char label[64] = "", uuid[40] = "";
    int fd, ok = 0;

    if (live == NULL && !strncmp(root, "/dev/", 5))
        return !strcmp(root, dev);
    if ((fd = open(dev, O_RDONLY | O_NONBLOCK)) < 0)
        return 0;
    if (live)
        ok = isolabel(fd, label, sizeof(label)) == 0 && !strcmp(label, live);
    else if (ext4ids(fd, uuid, sizeof(uuid), label, sizeof(label)) == 0)
        ok = (!strncmp(root, "UUID=", 5) && !strcasecmp(root + 5, uuid)) ||
             (!strncmp(root, "LABEL=", 6) && !strcmp(root + 6, label));
    close(fd);
    return ok;
}

static char *finddev(void) {
    static char dev[PATH_MAX];
    DIR *d;
    struct dirent *e;

    if (!(d = opendir("/sys/class/block")))
        return NULL;
    while ((e = readdir(d))) {
        if (e->d_name[0] == '.' || !strncmp(e->d_name, "loop", 4) ||
            !strncmp(e->d_name, "ram", 3) || !strncmp(e->d_name, "zram", 4))
            continue;
        snprintf(dev, sizeof(dev), "/dev/%s", e->d_name);
        if (wanted(dev)) {
            closedir(d);
            return dev;
        }
    }
    closedir(d);
    return NULL;
}

static void mountor(const char *src, const char *dst, const char *type,
                    unsigned long flags, const char *opts) {
    if (mount(src, dst, type, flags, opts) < 0)
        fail("mount %s on %s (%s): %s", src, dst, type, strerror(errno));
}

/* a read-only loop device over file, into dev */
static void setuploop(const char *file, char *dev, size_t len) {
    struct loop_config cfg;
    int ctl, n, ffd, lfd = -1, i;

    if ((ctl = open("/dev/loop-control", O_RDWR)) < 0)
        fail("/dev/loop-control: %s", strerror(errno));
    n = ioctl(ctl, LOOP_CTL_GET_FREE);
    close(ctl);
    if (n < 0)
        fail("no free loop device: %s", strerror(errno));
    snprintf(dev, len, "/dev/loop%d", n);
    if ((ffd = open(file, O_RDONLY)) < 0)
        fail("%s: %s", file, strerror(errno));
    for (i = 0; i < 50 && (lfd = open(dev, O_RDWR)) < 0; i++)
        usleep(100000); /* devtmpfs creates the node a moment later */
    if (lfd < 0)
        fail("%s: %s", dev, strerror(errno));
    memset(&cfg, 0, sizeof(cfg));
    cfg.fd = ffd;
    cfg.info.lo_flags = LO_FLAGS_READ_ONLY;
    if (ioctl(lfd, LOOP_CONFIGURE, &cfg) < 0)
        fail("%s: %s", dev, strerror(errno));
    close(ffd);
    close(lfd);
}

static void mountlive(const char *dev) {
    char file[PATH_MAX], loopdev[64], opts[PATH_MAX], upper[PATH_MAX],
        work[PATH_MAX];

    mkdir("/run/hos", 0755);
    mkdir(medium, 0755);
    mkdir(sfsdir, 0755);
    mkdir(overlaydir, 0755);
    mountor(dev, medium, "iso9660", MS_RDONLY, NULL);
    join(file, sizeof(file), medium, sfsfile);
    setuploop(file, loopdev, sizeof(loopdev));
    mountor(loopdev, sfsdir, "squashfs", MS_RDONLY, NULL);
    mountor("tmpfs", overlaydir, "tmpfs", 0, "mode=0755");
    join(upper, sizeof(upper), overlaydir, "upper");
    join(work, sizeof(work), overlaydir, "work");
    mkdir(upper, 0755);
    mkdir(work, 0755);
    if ((size_t)snprintf(opts, sizeof(opts),
                         "lowerdir=%s,upperdir=%s,workdir=%s", sfsdir, upper,
                         work) >= sizeof(opts))
        fail("overlay options too long");
    mountor("overlay", newroot, "overlay", 0, opts);
}

static void mountdisk(const char *dev) {
    static const char *const types[] = {"ext4", "xfs", "btrfs", "f2fs"};
    size_t i;

    for (i = 0; i < LEN(types); i++)
        if (mount(dev, newroot, types[i], rw ? 0 : MS_RDONLY, NULL) == 0)
            return;
    fail("mount %s on %s: %s", dev, newroot, strerror(errno));
}

static void copyfile(const char *src, const char *dst, mode_t mode) {
    static char buf[1 << 16];
    ssize_t n;
    int in, out;

    if ((in = open(src, O_RDONLY)) < 0)
        return;
    unlink(dst);
    if ((out = open(dst, O_WRONLY | O_CREAT | O_TRUNC, mode & 07777)) < 0) {
        close(in);
        return;
    }
    while ((n = read(in, buf, sizeof(buf))) > 0)
        if (write(out, buf, n) != n)
            break;
    close(in);
    close(out);
}

static void copytree(const char *src, const char *dst) {
    DIR *d;
    struct dirent *e;
    struct stat st;
    char s[PATH_MAX], t[PATH_MAX], link[PATH_MAX];
    ssize_t n;

    if (!(d = opendir(src)))
        return;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, ".."))
            continue;
        snprintf(s, sizeof(s), "%s/%s", src, e->d_name);
        snprintf(t, sizeof(t), "%s/%s", dst, e->d_name);
        if (lstat(s, &st) < 0)
            continue;
        if (S_ISDIR(st.st_mode)) {
            mkdir(t, st.st_mode & 07777);
            copytree(s, t);
        } else if (S_ISLNK(st.st_mode)) {
            if ((n = readlink(s, link, sizeof(link) - 1)) < 0)
                continue;
            link[n] = 0;
            unlink(t);
            if (symlink(link, t) < 0)
                msg("%s: %s", t, strerror(errno));
        } else if (S_ISREG(st.st_mode)) {
            copyfile(s, t, st.st_mode);
        }
    }
    closedir(d);
}

/* free the initramfs' memory: what ramfs holds stays allocated until the
 * files are gone, and the old root is unreachable after the switch */
static void rmtree(const char *path) {
    DIR *d;
    struct dirent *e;
    struct stat st;
    char p[PATH_MAX];

    if (!(d = opendir(path)))
        return;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, ".."))
            continue;
        snprintf(p, sizeof(p), "%s/%s", path, e->d_name);
        if (lstat(p, &st) == 0 && S_ISDIR(st.st_mode))
            rmtree(p);
        else
            unlink(p);
    }
    closedir(d);
    rmdir(path);
}

static void switchroot(void) {
    static const char *const moves[] = {"/dev", "/proc", "/sys", "/run"};
    char dst[PATH_MAX];
    size_t i;

    for (i = 0; i < LEN(moves); i++) {
        snprintf(dst, sizeof(dst), "%s%s", newroot, moves[i]);
        if (mount(moves[i], dst, NULL, MS_MOVE, NULL) < 0)
            msg("move %s: %s", moves[i], strerror(errno));
    }
    if (chdir(newroot) < 0 || mount(".", "/", NULL, MS_MOVE, NULL) < 0 ||
        chroot(".") < 0 || chdir("/") < 0)
        fail("switch_root: %s", strerror(errno));
    msg("starting %s", init);
    execl(init, init, (char *)NULL);
    fail("exec %s: %s", init, strerror(errno));
}

static void parsecmdline(void) {
    static char buf[4096];
    char *tok, *save;
    ssize_t n;
    int fd;

    if ((fd = open("/proc/cmdline", O_RDONLY)) < 0)
        fail("/proc/cmdline: %s", strerror(errno));
    n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    buf[n > 0 ? n : 0] = 0;
    init = defaultinit;
    for (tok = strtok_r(buf, " \t\n", &save); tok;
         tok = strtok_r(NULL, " \t\n", &save)) {
        if (!strcmp(tok, "hos.live"))
            live = livelabel;
        else if (!strncmp(tok, "hos.live=", 9))
            live = tok + 9;
        else if (!strncmp(tok, "root=", 5))
            root = tok + 5;
        else if (!strncmp(tok, "init=", 5))
            init = tok + 5;
        else if (!strcmp(tok, "rw"))
            rw = 1;
        else if (!strcmp(tok, "hos.debug"))
            verbose = 1;
    }
    if (!live && !root)
        fail("neither hos.live= nor root= on the kernel command line");
}

int main(void) {
    struct mod *m;
    char *dev;
    time_t deadline;
    size_t i;
    int fd;

    mountor("devtmpfs", "/dev", "devtmpfs", MS_NOSUID, "mode=0755");
    mountor("proc", "/proc", "proc", MS_NOSUID | MS_NOEXEC | MS_NODEV, NULL);
    mountor("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NOEXEC | MS_NODEV, NULL);
    mountor("tmpfs", "/run", "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755");
    if ((fd = open("/dev/console", O_RDWR)) >= 0) {
        dup2(fd, 0);
        dup2(fd, 1);
        dup2(fd, 2);
        if (fd > 2)
            close(fd);
    }

    parsecmdline();
    loadtables();
    for (i = 0; i < LEN(modules); i++)
        if ((m = findmod(modules[i])))
            loadmod(m);

    msg("waiting for %s%s", live ? "the live medium " : "", live ? live : root);
    deadline = time(NULL) + timeout;
    for (;;) {
        coldplug();
        if ((dev = finddev()))
            break;
        if (time(NULL) > deadline)
            fail("%s not found in %d seconds", live ? live : root, timeout);
        usleep(250000);
    }
    msg("root is %s", dev);
    if (live)
        mountlive(dev);
    else
        mountdisk(dev);

    if (access(updates, F_OK) == 0) {
        msg("applying %s", updates);
        copytree(updates, newroot);
        rmtree(updates);
    }
    rmtree(modroot);
    switchroot();
    return 1;
}
