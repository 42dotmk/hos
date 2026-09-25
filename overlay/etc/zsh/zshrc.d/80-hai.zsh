# hai.zsh - run the current line through hai instead of the old gpt bindings.
# ^o        ask hai to do the command (its reply is the answer)
# ^z        frame it as "what does this command do"
# ^C-c      frame it as "write the code for this"
# The binding runs hai in the current directory, so in a project it is the
# terminal agent for that project.

_hai_run(){
    local prev=$BUFFER
    if [ -z "$prev" ]; then
        zle reset-prompt
        return
    fi
    BUFFER=""
    zle -I && zle redisplay
    hai say "$1 $prev"
    print -s "$prev"
}

_hai_plain(){ _hai_run "" }
_hai_ask(){ _hai_run "What does this command do?" }
_hai_code(){ _hai_run "Write the code for:" }

zle -N _hai_plain
zle -N _hai_ask
zle -N _hai_code

bindkey '^o' _hai_plain
bindkey '^z' _hai_ask
bindkey '\Mc' _hai_code
