# compinit: rebuild the dump once a day, otherwise trust the cache
autoload -Uz compinit
if [[ -n ~/.zcompdump(#qN.mh+24) || ! -s ~/.zcompdump ]]; then
    compinit
else
    compinit -C
fi
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Za-z}'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"

# fzf: ** completion and ctrl-r/ctrl-t/alt-c
for f in /usr/share/fzf/completion.zsh /usr/share/fzf/key-bindings.zsh; do
    [[ -r $f ]] && source $f
done
