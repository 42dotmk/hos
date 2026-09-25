# hos's completion overrides first (_pass: escapes [ ] in entry names)
fpath=(/etc/zsh/completions $fpath)

# compinit: the full check at most once a day, otherwise trust the cache.
# Touch the dump after it: compinit leaves it as is when nothing changed,
# and the check would then run on every shell.
autoload -Uz compinit
if [[ -n ~/.zcompdump(#qN.mh+24) || ! -s ~/.zcompdump ]]; then
    compinit && touch ~/.zcompdump
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
