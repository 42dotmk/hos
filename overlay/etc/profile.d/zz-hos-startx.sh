# hos: the live user is autologged in on tty1 — go straight into X.
# Named zz- so /etc/profile sources it after locale.sh: it exports LANG
# from /etc/locale.conf, and X must inherit it or every terminal in the
# session runs in the C locale (fastfetch's logo turns into \u{} escapes).
# Not exec'd on purpose: when hwm exits (or X fails) you land in a
# shell instead of agetty's autologin looping back into startx.
if [ -z "$DISPLAY" ] && [ "$(tty)" = /dev/tty1 ] && command -v startx >/dev/null; then
    startx
fi
