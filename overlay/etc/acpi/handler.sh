#!/bin/sh
# hos's acpid handler (Void's calls elogind for the lid and a zzz it does
# not ship): power button powers off, sleep button and lid suspend through
# zzz, brightness keys step the backlight. $1 is the event group, $2 the
# device, $3 the state.
case "$1:$3" in
button/power:*) poweroff ;;
button/sleep:*) zzz ;;
button/lid:close) zzz ;;
video/brightnessdown:*) brightnessctl -q set 5%- ;;
video/brightnessup:*) brightnessctl -q set 5%+ ;;
esac
