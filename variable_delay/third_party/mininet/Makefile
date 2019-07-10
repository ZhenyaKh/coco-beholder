MNEXEC = vdlocalmnexec

CFLAGS += -Wall -Wextra

all: vdlocalmnexec

clean:
	rm -f *.pyc $(MNEXEC)

vdlocalmnexec: mnexec.c net.py
	cc $(CFLAGS) $(LDFLAGS) $< -o $@

