# hos — the hackable distribution as a bootable ISO: a root filesystem
# from the Void repositories (xbps) with the hackable tools staged into it,
# hos's own init in an initramfs it builds itself, hsmd as pid 1, and a
# grub boot menu, packed by grub-mkrescue.
#
# make            build the ISO (rootfs if needed, stage, initramfs, iso)
# make rootfs     xbps-install PACKAGES into build/rootfs (network; once)
# make packages   build the tools, pack them as xbps packages into build/repo
# make stage      overlay, packages, sources, fonts, user, services into the rootfs
# make initramfs  build/initramfs from init/ and the rootfs's modules
# make qemu       boot the newest ISO with kvm
# make usb-install USB=/dev/sdX   the ISO dd'd onto a stick (asks for sudo)
# make vmtest     boot it headless with a fresh hsmd injected, check init works
# make sign       sign build/repo with KEY (the private key CI holds as a secret)
# make clean      remove build/; distclean also removes ISOs
#
# No sudo: everything that needs root runs in a user namespace (unshare
# --map-auto, which wants a /etc/subuid line for you); as real root (CI)
# it runs directly. Needs xbps, rsync, cpio, zstd, squashfs-tools, grub,
# grub-x86_64-efi, xorriso, mtools, python3 (splash) and the tools' deps.

HACKABLE = ..
PROJECTS ?= hed hterm hwm hws htray hnd hmenu hsm hml hstt hweb hbg hai

ARCH      = x86_64
BUILD     = build
ROOTFS    = $(BUILD)/rootfs
CACHE     = $(BUILD)/xbps-cache
INITRAMFS = $(BUILD)/initramfs
REPODIR   = $(BUILD)/repo
ISODIR    = $(BUILD)/iso
VERSION  ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
ISO       = hos-$(VERSION)-$(ARCH).iso
LOCALE    = en_US.UTF-8
REPO     ?= https://repo-default.voidlinux.org/current
FONTSRC  ?= fonts
BGSRC    ?= backgrounds
NS       ?= $(shell [ "$$(id -u)" = 0 ] || echo unshare --user --map-root-user --map-auto --mount)
export HACKABLE PROJECTS VERSION LOCALE REPO FONTSRC BGSRC REPODIR

all: iso

init/init: init/init.c init/config.h
	$(MAKE) -C init

projects:
	for p in $(PROJECTS); do $(MAKE) -C $(HACKABLE)/$$p || exit 1; done

# the package install is the slow, network-bound step: once, then only when
# the lists change. Everything else is re-staged on top every build.
$(ROOTFS)/.installed: PACKAGES IGNORE mkrootfs
	$(NS) sh -c './mkrootfs install $(ROOTFS) $(CACHE) && touch $@'

rootfs: $(ROOTFS)/.installed

# the tools as xbps packages (mkpkg builds them, in their trees, as the
# user): what stage installs into the rootfs, what CI signs and publishes
packages: rootfs
	./mkpkg $(ROOTFS) $(REPODIR)

# the repository signature, and one per package; KEY is the private half
# of hos-repo.pub (CI: the XBPS_PRIVKEY secret). Remote repos must be signed.
sign:
	test -n "$(KEY)" || { echo "make sign KEY=/path/to/private.pem"; exit 1; }
	xbps-rindex --privkey $(KEY) --signedby "hos" --sign $(REPODIR)
	xbps-rindex --privkey $(KEY) --signedby "hos" --sign-pkg $(REPODIR)/*.xbps

stage: packages init/init
	$(NS) ./mkrootfs stage $(ROOTFS)

initramfs: stage
	$(NS) sh -c 'overlay/usr/bin/hos-mkinitramfs -i init/init \
		-m $(ROOTFS)/lib/modules/* -o $(INITRAMFS) $$(ls $(ROOTFS)/lib/modules)'

# boot menu background (640x480), drawn from the fastfetch logo so the two match
splash.png: splash.py overlay/usr/share/hos/logo.txt
	python3 splash.py $@

iso: initramfs splash.png
	$(NS) ./mkiso $(ROOTFS) $(INITRAMFS) $(ISODIR) $(ISO)

print-projects:
	@echo $(PROJECTS)

# brand the running machine like the ISO: fastfetch logo + config and
# the hos os-release. Needs sudo, so the user runs it. /etc/os-release
# is base-files' (a symlink to /usr/lib/os-release, not a conf file), so
# a base-files update puts Void's back — rerun this after one.
install-host:
	sudo install -Dm644 overlay/usr/share/hos/logo.txt /usr/share/hos/logo.txt
	sudo install -Dm644 overlay/etc/fastfetch/config.jsonc /etc/fastfetch/config.jsonc
	sudo rm -f /etc/os-release
	sudo install -m644 overlay/etc/os-release /etc/os-release

# virtio-vga advertises xres/yres as the display's preferred mode, so the
# guest (console and X alike) comes up at the host monitor's resolution
# instead of the emulated VGA's fixed 1280x800; falls back to 1920x1080
# when there is no X to ask
RES = $(shell xrandr --current 2>/dev/null | awk '/ connected primary/ {print $$4}' | cut -d+ -f1)
XRES = $(word 1,$(subst x, ,$(if $(RES),$(RES),1920x1080)))
YRES = $(word 2,$(subst x, ,$(if $(RES),$(RES),1920x1080)))

qemu:
	qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m 4G \
		-device virtio-vga,xres=$(XRES),yres=$(YRES) \
		-cdrom "$$(ls -t hos-*.iso | head -1)"

# write the newest ISO raw onto a usb stick: mkusb does the work (detects
# the stick, refuses partitions, mounted devices and the disk hos runs from,
# asks for a pick when there are several). USB= names the device when
# detection cannot know you mean it.
usb-install:
	./mkusb $(USB)

# boot the newest ISO headless with a fresh hsmd injected and check that
# it works as init (see vmtest.py)
vmtest:
	python3 vmtest.py pid1
	python3 vmtest.py reboot

# build/ is owned by the namespace's root (subuids), so it is removed there
clean:
	$(NS) rm -rf $(BUILD)
	$(MAKE) -C init clean

distclean: clean
	rm -f hos-*.iso

.PHONY: all projects rootfs packages sign stage initramfs iso install-host print-projects qemu usb-install vmtest clean distclean
