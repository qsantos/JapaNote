FORMS:=$(wildcard *.ui)
TARGETS:=$(FORMS:.ui=_qt5.py) $(FORMS:.ui=_qt6.py)

all: $(TARGETS)

%_qt5.py: %.ui
	pyuic5 $< -o $@

%_qt6.py: %.ui
	pyuic6 $< -o $@

clean:
	rm -f $(TARGETS)

.PHONY: all clean
