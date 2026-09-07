# suggestions from history (ctrl-space or → accepts); highlighting last
p=/usr/share/zsh/plugins
if [[ -r $p/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
    source $p/zsh-autosuggestions/zsh-autosuggestions.zsh
    bindkey '^ ' autosuggest-accept
fi
[[ -r $p/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]] &&
    source $p/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
unset p
