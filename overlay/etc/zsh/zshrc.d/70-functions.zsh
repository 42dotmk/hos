# later: move files/dirs to ~/_fix for dealing with later
later() {
    local dest=$HOME/_fix f base target
    (( $# )) || { print -u2 "usage: later <file|dir>..."; return 1; }
    mkdir -p "$dest" || return 1
    for f in "$@"; do
        [[ -e $f || -L $f ]] || { print -u2 "later: not found: $f"; continue; }
        base=${f:t}
        target=$dest/$base
        [[ -e $target || -L $target ]] && target=$dest/$base.$(date +%Y%m%d-%H%M%S)
        mv -- "$f" "$target" && print "moved: $f -> $target"
    done
}

# pick a branch with fzf; remote ones get a tracking branch
fzf_git_branch() {
    git rev-parse HEAD >/dev/null 2>&1 || return
    git branch -a -vv --color=always | fzf --height 40% --ansi --multi --tac \
        | sed 's/^..//' | awk '{print $1}'
}
fzf_git_checkout() {
    local branch=$(fzf_git_branch)
    [[ -n $branch ]] || { echo "No branch selected."; return; }
    if [[ $branch == remotes/* ]]; then
        git checkout --track "$branch"
    else
        git checkout "$branch"
    fi
}
