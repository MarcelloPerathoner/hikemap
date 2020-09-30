# include ../Variables.mak

NODE := ../node_modules/.bin

WEBPACK            := $(NODE)/webpack --no-color
WEBPACK_DEV_SERVER := $(NODE)/webpack-dev-server --no-color
ESLINT             := $(NODE)/eslint -f unix
STYLELINT          := $(NODE)/stylelint -f unix

.PHONY: build build-production

AUX := dist/api.conf.js

dist/api.conf.js: src/api.conf.js
	mkdir -p dist
	cp $< $@

build: $(AUX)
	$(WEBPACK) --config webpack.dev.js

build-production: clean $(AUX)
	$(WEBPACK) --config webpack.prod.js

dev-server: $(AUX)
	$(WEBPACK_DEV_SERVER) --config webpack.dev.js

dev-server-debug: $(AUX)
	env DEBUG="express:*" $(WEBPACK_DEV_SERVER) --config webpack.dev.js

dev-server-production: clean $(AUX)
	$(WEBPACK_DEV_SERVER) --config webpack.prod.js

upload: build
	$(RSYNC) --exclude "api.conf.js" build/* $(HOST_CLIENT)

lint: eslint csslint

eslint:
	$(ESLINT) src/components/*.vue src/js/*.js src/*.js *.js *.json

csslint:
	$(STYLELINT) src/components/*.vue src/less/*.less

clean:
	rm -rf build/*
	find . -name "*~" -delete

build/index.html: src/index.html
	-mkdir -p build
	cp $< $@

build/api.conf.js: src/api.conf.js
	-mkdir -p build
	cp $< $@
