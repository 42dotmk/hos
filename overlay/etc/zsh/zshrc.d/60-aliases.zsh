alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias .....='cd ../../../..'
alias ......='cd ../../../../..'

alias rmrf='rm -rf'
alias rg='rg --hidden'
alias q='exit'
alias cls='clear'
# sudo asks through hmenu-askpass (SUDO_ASKPASS, 50-env) - only under X:
# on a console hmenu cannot show, and sudo -A would have no way to ask
[[ -n $DISPLAY ]] && alias sudo='sudo -A'
alias i='sudo xbps-install'
alias u='sudo xbps-install -Su'
alias fbo='find . -iname bin -o -iname obj | xargs rm -rf'

alias e="$EDITOR"
alias o='hed .'
alias mail='hed -c mail'
alias fe='fzf | xargs -o $EDITOR'
alias fp='fzf | xargs -o bat'

alias cat='bat'
alias ls='ls --color=auto'
alias l='eza'
alias ll='eza -al'
alias lal='eza -al'
alias la='eza -a'
alias lt='eza --tree'
alias l2='eza -T -L 2'
alias l3='eza -T -L 3'
alias l4='eza -T -L 4'

# fasd: s is fasd's select (it was sudo, then fasd in the dotfiles too)
alias a='fasd -a'        # any
alias s='fasd -si'       # show / search / select
alias f='fasd -f'        # file
alias sd='fasd -sid'     # interactive directory selection
alias sf='fasd -sif'     # interactive file selection
alias j='fasd_cd -d'     # cd, same functionality as j in autojump

alias p='pass -c'
alias pbcopy='xsel --clipboard --input'
alias pbpaste='xsel --clipboard --output'
alias open='xdg-open'

alias t='tmux'
alias ta='tmux a'
alias tls='tmux ls'
alias tsend='tmux send-keys -t'

alias m='make'
alias mb='make build'
alias mc='make clean'
alias mr='make run'
alias mrr='make watch'
alias mex='make example'
alias mrt='make test'

alias weather="curl -s http://wttr.in/ | grep -o '^[^<]*'"

# tools hos does not ship: the alias appears once the tool is installed
(( $+commands[python3] )) && alias fserve='python3 -m http.server 3333'
(( $+commands[acpi] )) && alias batery='acpi -b'
(( $+commands[espeak] )) && alias speak='espeak -v en+f2'
(( $+commands[bc] )) && alias calc='bc --interactive --quiet'
if (( $+commands[http] )); then
    alias get='http GET'
    alias post='http POST'
    alias put='http PUT'
    alias delete='http DELETE'
fi
