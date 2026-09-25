export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
export EDITOR=hed VISUAL=hed PAGER=less
export XDG_SCREENSHOTS_DIR=$HOME/screenshots
export NO_AT_BRIDGE=1                # no screen reader: stop GTK spawning at-spi
[[ -n $DISPLAY ]] && export XDG_SESSION_TYPE=x11
# sudo -A asks for the password in an hmenu; sudo wants the full path
export SUDO_ASKPASS=/usr/bin/hmenu-askpass
export ELECTRON_OZONE_PLATFORM_HINT=auto

# ~/.local/bin first of hos's own (make install symlinks the tools
# there), then where the toolchains install themselves; a directory that
# is not there yet costs nothing
# fnm: its default node straight on PATH, not `eval "$(fnm env)"`, which
# runs fnm and makes a multishell dir on every startup (~40ms)
export FNM_DIR=$HOME/.local/share/fnm
path=($FNM_DIR $FNM_DIR/aliases/default/bin $HOME/.bun/bin $HOME/.pixi/bin
      $HOME/.local/share/uv/tools $HOME/.local/bin $HOME/.cargo/bin
      $HOME/.dotnet/tools $HOME/.dotnet $path)
export DOTNET_ROOT=$HOME/.dotnet BUN_INSTALL=$HOME/.bun
[[ -s $HOME/.bun/_bun ]] && source $HOME/.bun/_bun
export POETRY_VIRTUALENVS_PROMPT="🐍" POETRY_VIRTUALENVS_IN_PROJECT=true

# 90-plugins binds ctrl-space itself
export ZSH_AUTOSUGGEST_MANUAL_REBIND=true

# fasd: frecent files and dirs; its init is cached per user, redone when
# fasd is newer than the cache. Its own aliases come first, 60-aliases
# sets the ones used here.
if (( $+commands[fasd] )); then
    # a fresh home has neither ~/.cache nor fasd's data file, and fasd's
    # first write into a missing one fails under gawk (it cannot read it)
    # and is lost: make both, empty
    fasd_data=${_FASD_DATA:-${XDG_CACHE_HOME:-$HOME/.cache}/fasd}
    [[ -e $fasd_data ]] || { mkdir -p ${fasd_data:h} && : >| $fasd_data }
    unset fasd_data
    fasd_cache=$HOME/.fasd-init-zsh
    if [[ $commands[fasd] -nt $fasd_cache || ! -s $fasd_cache ]]; then
        fasd --init posix-alias zsh-hook zsh-ccomp zsh-ccomp-install >| $fasd_cache
    fi
    source $fasd_cache
    unset fasd_cache
fi
