FORMS:=$(wildcard *.ui)
TARGETS:=$(FORMS:.ui=_qt5.py) $(FORMS:.ui=_qt6.py)

all: $(TARGETS)

%_qt5.py: %.ui
	pyuic5 $< -o $@

%_qt6.py: %.ui
	pyuic6 $< -o $@

clean:
	rm -f $(TARGETS)

package:
	zip -r japanote.ankiaddon *.py edict2/*.py edict2/deinflect.dat edict2/edict2 edict2/enamdict edict2/kanjidic

.PHONY: all clean
