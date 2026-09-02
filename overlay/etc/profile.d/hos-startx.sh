# hos: the live user is autologged in on tty1 — go straight into X.
# Not exec'd on purpose: when hwm exits (or X fails) you land in a
# shell instead of agetty's autologin looping back into startx.
if [ -z "$DISPLAY" ] && [ "$(tty)" = /dev/tty1 ] && command -v startx >/dev/null; then
    startx
fi
