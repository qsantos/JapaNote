FORMS:=$(wildcard *.ui)
TARGETS:=$(FORMS:.ui=4.py) $(FORMS:.ui=5.py)

all: $(TARGETS)

%5.py: %.ui
	pyuic5 $< -o $@

%4.py: %.ui
	pyuic4 $< -o $@

clean:
	rm -f $(TARGETS)

.PHONY: all clean
