ID := plugin.video.kodipopcorntime
VERSION := $(shell xmllint --xpath 'string(//addon/@version)' $(ID)/addon.xml)
ARCHIVE := $(ID)-$(VERSION).zip

.PHONY: all clean $(ARCHIVE)

all: $(ARCHIVE)

archive:
	mkdir archive

clean:
	git clean -dfX

$(ARCHIVE): archive
	git archive -o $(ARCHIVE) HEAD $(ID)
	fuse-zip $(ARCHIVE) archive
	chmod -x archive/$(ID)/resources/bin/*/*
	umount archive
