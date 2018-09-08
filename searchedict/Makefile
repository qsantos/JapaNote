TARGETS:=formbrowser4.py formsettings4.py formguessids4.py formbrowser5.py formsettings5.py formguessids5.py

all: $(TARGETS)

%5.py: %.ui
	pyuic5 $< -o $@

%4.py: %.ui
	pyuic4 $< -o $@

clean:
	rm -f $(TARGETS)

.PHONY: all clean
