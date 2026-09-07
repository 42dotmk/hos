git_current_branch() { git symbolic-ref --quiet --short HEAD 2>/dev/null; }
git_main_branch() {
    local b
    for b in main master trunk; do
        git show-ref -q --verify refs/heads/$b && { echo $b; return; }
    done
    echo main
}

alias g='git'
alias ga='git add'
alias gaa='git add --all'
alias gap='git apply'

alias gb='git branch --show-current'
alias gba='git branch -a'
alias gbd='git branch -d'
alias gbD='git branch -D'
alias gbl='git blame -b -w'
alias gbr='git branch --remote'

alias gc='git commit -v'
alias gca='git commit -v -a'
alias gcam='git commit -a -m'
alias gcmsg='git commit -m'
alias gcb='git checkout -b'
alias gcm='git checkout $(git_main_branch)'
alias gco='fzf_git_checkout'
alias gcl='git clone --recurse-submodules'
alias gcl1='git clone --depth=1'
alias gclean='git clean -id'
alias gcount='git shortlog -sn'
alias gcp='git cherry-pick'
alias gcpa='git cherry-pick --abort'
alias gcpc='git cherry-pick --continue'

alias gf='git fetch'
alias gfa='git fetch --all --prune'
alias gl='git pull'
alias gpr='git pull --rebase'
alias ggpull='git pull origin "$(git_current_branch)"'
alias gp='git push'
alias gpd='git push --dry-run'
alias gpf='git push --force-with-lease'
alias gpsup='git push --set-upstream origin $(git_current_branch)'
alias ggpush='git push origin "$(git_current_branch)"'

alias gds='git diff --staged'
alias gdw='git diff --word-diff'
alias glg='git log --stat'
alias glgp='git log --stat -p'
alias glo='git log --oneline --decorate'
alias glog='git log --oneline --decorate --graph'
alias gloga='git log --oneline --decorate --graph --all'
alias glol="git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset'"
alias glola="git log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --all"

alias gm='git merge'
alias gma='git merge --abort'
alias gmom='git merge origin/$(git_main_branch)'
alias grb='git rebase'
alias grba='git rebase --abort'
alias grbc='git rebase --continue'
alias grbi='git rebase -i'
alias grhh='git reset --hard'
alias gr='git remote'
alias grv='git remote -v'

alias gst='git status'
alias gss='git status -s'
alias gsb='git status -sb'
alias gsh='git show'
alias gsw='git switch'
alias gstl='git stash list'
alias gstp='git stash pop'
alias gsta='git stash apply'
alias gstd='git stash drop'
