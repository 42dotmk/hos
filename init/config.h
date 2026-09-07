/* hos init - compile-time configuration */

/* the kernel command line names the root: "hos.live[=LABEL]" is the live
 * medium (an iso9660 volume with this label, LABEL defaults to livelabel),
 * "root=UUID=|LABEL=|/dev/..." a disk. "init=" is what to exec afterwards,
 * "rw" mounts a disk root read-write, "hos.debug" logs every step. */
static const char livelabel[] = "HOS";
static const char defaultinit[] = "/usr/bin/hsmd";

/* seconds to wait for the root device; usb sticks enumerate slowly */
static const int timeout = 30;

/* modules loaded before looking at the hardware: the filesystems, the block
 * layer bits nothing announces through a modalias, the paravirt drivers.
 * Anything else is loaded by matching /sys/bus/.../modalias against
 * modules.alias, like udev does. A name not in the initramfs is skipped. */
static const char *const modules[] = {
    "loop",     "squashfs",   "overlay",      "isofs",       "ext4",
    "sd_mod",   "sr_mod",     "usb_storage",  "uas",         "nvme",
    "ahci",     "vmd",        "mmc_block",    "virtio_pci",  "virtio_blk",
    "virtio_scsi",
};

/* the live root: the medium mounted here, its squashfs on a loop device
 * mounted next to it, and a tmpfs overlay on top that becomes /. /run is
 * moved into the new root, so these paths stay valid after the switch. */
static const char moddir[] = "/lib/modules";
static const char newroot[] = "/newroot";
static const char medium[] = "/run/hos/medium";
static const char sfsfile[] = "hos.sfs"; /* on the medium */
static const char sfsdir[] = "/run/hos/sfs";
static const char overlaydir[] = "/run/hos/overlay"; /* upper/ and work/ */

/* a tree here (cpio appended to the initramfs, see vmtest.py) is copied
 * over the new root before switching: a way to try a binary or a boot
 * script without rebuilding the iso */
static const char updates[] = "/updates";
