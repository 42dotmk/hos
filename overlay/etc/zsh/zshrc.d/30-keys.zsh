bindkey -e
bindkey '^I' expand-or-complete
bindkey '^[[A' history-beginning-search-backward   # up: prefix history
bindkey '^[[B' history-beginning-search-forward
bindkey '^[[H' beginning-of-line                   # home/end/delete
bindkey '^[[F' end-of-line
bindkey '^[[3~' delete-char
bindkey '^[[1;5C' forward-word                     # ctrl-left/right
bindkey '^[[1;5D' backward-word
