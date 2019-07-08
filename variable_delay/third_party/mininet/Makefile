MNEXEC = mnexec

CFLAGS += -Wall -Wextra

all: mnexec

clean:
	rm -f *.pyc $(MNEXEC)

mnexec: mnexec.c net.py
	cc $(CFLAGS) $(LDFLAGS) $< -o $@

