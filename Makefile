# hos — bootable Void Linux ISO carrying the hackable tools.
#
# make            build the ISO (fetches void-mklive on first run; the
#                 mklive step runs under sudo)
# make stage      assemble build/overlay only — sources, symlinks, fonts
# make qemu       boot the newest ISO with kvm
# make clean      remove build/; distclean also removes ISOs

HACKABLE = ..
PROJECTS = hed hterm hwm hws htray hnd hmenu hsm hml hstt hweb hbg

ARCH    = x86_64
BUILD   = build
MKLIVE  = $(BUILD)/void-mklive
OVERLAY = $(BUILD)/overlay
CACHE   = $(BUILD)/xbps-cachedir-$(ARCH)
SRC     = usr/src/hackable
ISO     = hos-$(shell date +%Y%m%d)-$(ARCH).iso

# hterm's config.h compiles in absolute paths to exactly these files
FONTDIR = $(HOME)/.local/share/fonts
FONTS   = IosevkaNerdFontMono-Regular.ttf IosevkaNerdFontMono-Bold.ttf \
          IosevkaNerdFontMono-Italic.ttf IosevkaNerdFontMono-BoldItalic.ttf

# hbg's config.h reads ~/pictures/backgrounds/preffered; ship a few for
# the live user (via /etc/skel) and root
BGDIR   = pictures/backgrounds/preffered
BGS     = planets.png planets2.jpeg 4lieves.png 3doyourwork.jpeg

# build artifacts too big to ship; the sources stay, so it rebuilds in place
RSYNC_EXCLUDES = --exclude=.git --exclude=/vendor/whisper.cpp/build

# PACKAGES / SERVICES / IGNORE: one name per line, # comments
list = $$(grep -v '^\#' $(CURDIR)/$(1) | tr '\n' ' ')

all: iso

$(MKLIVE)/mklive.sh:
	mkdir -p $(BUILD)
	git clone --depth 1 https://github.com/void-linux/void-mklive $(MKLIVE)

# the live user is created at boot by mklive's dracut module, which
# hardcodes the void-live hostname and the voidlinux passwords
$(MKLIVE)/.hos-patched: $(MKLIVE)/mklive.sh
	sed -i 's/void-live/hos/g; s/voidlinux/hos/g' $(MKLIVE)/dracut/vmklive/adduser.sh
	touch $@

stage:
	for p in $(PROJECTS); do $(MAKE) -C $(HACKABLE)/$$p || exit 1; done
	rm -rf $(OVERLAY)
	mkdir -p $(OVERLAY)/$(SRC) $(OVERLAY)/usr/bin
	cp -a overlay/. $(OVERLAY)/
	for p in $(PROJECTS); do \
		rsync -a $(RSYNC_EXCLUDES) $(HACKABLE)/$$p/ $(OVERLAY)/$(SRC)/$$p/ || exit 1; \
	done
	for p in $(PROJECTS); do \
		case $$p in \
		hed) bins="build/hed build/tsi" ;; \
		hsm) bins="hsmd hsm" ;; \
		*)   bins="$$p" ;; \
		esac; \
		for b in $$bins; do \
			ln -sfn /$(SRC)/$$p/$$b $(OVERLAY)/usr/bin/$${b##*/} || exit 1; \
		done; \
	done
	mkdir -p $(OVERLAY)$(FONTDIR) $(OVERLAY)/usr/share/fonts/hackable
	for f in $(FONTS); do \
		cp $(FONTDIR)/$$f $(OVERLAY)$(FONTDIR)/ && \
		cp $(FONTDIR)/$$f $(OVERLAY)/usr/share/fonts/hackable/ || exit 1; \
	done
	for h in etc/skel root; do \
		mkdir -p $(OVERLAY)/$$h/$(BGDIR) && \
		for b in $(BGS); do \
			cp $(HOME)/$(BGDIR)/$$b $(OVERLAY)/$$h/$(BGDIR)/ || exit 1; \
		done; \
	done

# paths must be absolute: xbps resolves a relative -c against the install
# rootdir, which for the target is inside the image tree — a relative
# cache dir ends up on the ISO
iso: $(MKLIVE)/.hos-patched stage
	cd $(MKLIVE) && sudo ./mklive.sh -a $(ARCH) -T "hos linux" \
		-p "$(call list,PACKAGES)" -S "$(call list,SERVICES)" \
		-g "$(call list,IGNORE)" \
		-C "live.user=hos live.autologin" \
		-c $(CURDIR)/$(CACHE) -H $(CURDIR)/$(CACHE) \
		-I $(CURDIR)/$(OVERLAY) -o $(CURDIR)/$(ISO)
	sudo chown "$$(id -u):$$(id -g)" $(ISO)

qemu:
	qemu-system-x86_64 -enable-kvm -m 4G -cdrom "$$(ls -t hos-*.iso | head -1)"

clean:
	rm -rf $(BUILD)

distclean: clean
	rm -f hos-*.iso

.PHONY: all stage iso qemu clean distclean
