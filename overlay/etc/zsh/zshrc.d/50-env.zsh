export EDITOR=hed VISUAL=hed PAGER=less
export PATH=$HOME/.local/bin:$PATH   # make install symlinks the tools here
export NO_AT_BRIDGE=1                # no screen reader: stop GTK spawning at-spi
[[ -n $DISPLAY ]] && export XDG_SESSION_TYPE=x11
