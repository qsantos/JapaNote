FORMS:=$(wildcard *.ui)
TARGETS:=$(FORMS:.ui=_qt5.py) $(FORMS:.ui=_qt6.py)

all: package

%_qt5.py: %.ui
	pyuic5 $< -o $@

%_qt6.py: %.ui
	pyuic6 $< -o $@

clean:
	rm -f $(TARGETS)

package: $(TARGETS)
	# the dictionaries are not packaged: the add-on downloads them (see resources.py)
	rm -f japanote.ankiaddon
	zip japanote.ankiaddon *.py deinflect.dat

.PHONY: all clean package
