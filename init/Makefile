# hos init: the initramfs' /init, static so it needs nothing else in there
CC     ?= cc
CFLAGS  = -std=c11 -pedantic -Wall -Wextra -Os -D_GNU_SOURCE

init: init.c config.h
	$(CC) $(CFLAGS) -static -o $@ init.c

clean:
	rm -f init

.PHONY: clean
