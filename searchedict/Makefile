FORMS:=$(wildcard *.ui)
TARGETS:=$(FORMS:.ui=.py)

all: $(TARGETS)

%.py: %.ui
	pyuic5 $< -o $@

clean:
	rm -f $(TARGETS)

.PHONY: all clean
