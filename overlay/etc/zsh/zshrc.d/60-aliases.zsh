alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias .....='cd ../../../..'

alias ls='ls --color=auto'
alias l='ls'
alias ll='ls -l'
alias la='ls -a'
alias lal='ls -al'
alias rg='rg --hidden'
alias rmrf='rm -rf'
alias q='exit'
alias cls='clear'
alias s='sudo'
alias i='sudo xbps-install'
alias u='sudo xbps-install -Su'

alias e="$EDITOR"
alias o='hed .'
alias mail='hed -c mail'
alias fe='fzf | xargs -o $EDITOR'
alias fp='fzf | xargs -o less'

alias p='pass -c'
alias pbcopy='xclip -selection clipboard -i'
alias pbpaste='xclip -selection clipboard -o'
alias open='xdg-open'

alias t='tmux'
alias ta='tmux a'
alias tls='tmux ls'
alias send='tmux send-keys -t'

alias m='make'
alias mb='make build'
alias mc='make clean'
alias mr='make run'
alias mrt='make test'

alias fserve='python3 -m http.server 3333'
alias weather="curl -s http://wttr.in/ | grep -o '^[^<]*'"
