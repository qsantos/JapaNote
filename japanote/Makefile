all: package

# the dictionaries are not packaged: the add-on downloads them (see resources.py); the manifest is
# used when installing the package from a file, but ignored when installing from AnkiWeb
package:
	rm -f japanote.ankiaddon
	zip japanote.ankiaddon *.py deinflect.dat manifest.json

.PHONY: all package
