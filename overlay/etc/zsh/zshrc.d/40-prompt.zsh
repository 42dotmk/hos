# dir, git branch, and user@host only when it matters (root or ssh)
autoload -Uz vcs_info
zstyle ':vcs_info:*' enable git
zstyle ':vcs_info:git:*' formats ' %F{yellow}%b%f'
zstyle ':vcs_info:git:*' actionformats ' %F{yellow}%b|%a%f'
precmd() { vcs_info }
setopt prompt_subst
if [[ $EUID == 0 || -n $SSH_CONNECTION ]]; then
    PROMPT='%F{red}%n@%m%f %F{blue}%~%f${vcs_info_msg_0_} %# '
else
    PROMPT='%F{blue}%~%f${vcs_info_msg_0_} %# '
fi
