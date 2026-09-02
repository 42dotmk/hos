# hos: a small zshrc so a fresh login gets a usable shell (and not the
# zsh-newuser-install wizard). Replace freely.
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt hist_ignore_dups share_history autocd
bindkey -e
autoload -Uz compinit && compinit
zstyle ':completion:*' menu select
PROMPT='%F{blue}%n@%m%f %~ %# '
export EDITOR=hed VISUAL=hed
alias ls='ls --color=auto' ll='ls -l' la='ls -la'
