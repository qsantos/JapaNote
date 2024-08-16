FORMS:=$(wildcard *.ui)
TARGETS:=$(FORMS:.ui=.py)

all: $(TARGETS)

%.py: %.ui
	pyuic6 $< -o $@

clean:
	rm -f $(TARGETS)

.PHONY: all clean
