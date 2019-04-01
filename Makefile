GEO_FABRIK  = https://download.geofabrik.de
OSM_DUMP    = europe/italy/nord-est-latest.osm.pbf
OSM_UPDATES = europe/italy/nord-est-updates/
OSM_BASE    = $(notdir $(OSM_DUMP))
OSM_CARTO   = ../openstreetmap-carto
SRTM         = ../srtm-stylesheets

PGHOST     = localhost
PGUSER     = osm
PGDATABASE = osm
PGPASSWORD := $(shell apg -a 1 -m 12 -n 1 -E ":'")

SU_PSQL = sudo -u postgres psql
PSQL    = psql -d $(PGDATABASE)
CARTO   = ~/.npm-global/bin/carto

DATADIR = $(CURDIR)/data

MSS := $(wilcard *.mss)

all: xml

prereq:
	sudo apt-get install apg osm2pgsql sed wget \
		fonts-noto-cjk fonts-noto-hinted fonts-noto-unhinted fonts-hanazono ttf-unifont

create_db:
	$(SU_PSQL) -c "CREATE ROLE $(PGUSER) LOGIN PASSWORD '$(PGPASSWORD)'"
	echo "$(PGHOST):*:$(PGDATABASE):$(PGUSER):$(PGPASSWORD)" >> ~/.pgpass
	$(SU_PSQL) -c "CREATE DATABASE $(PGDATABASE) OWNER $(PGUSER)"
	$(SU_PSQL) -d $(PGDATABASE) -c "CREATE EXTENSION postgis; CREATE EXTENSION hstore"

clean_db:
	$(SU_PSQL) -c "DROP DATABASE $(PGDATABASE)"
	$(SU_PSQL) -c "DROP ROLE $(PGUSER)"
	sed -i.bak "/^$(PGHOST):\*:$(PGDATABASE):$(PGUSER):/d" ~/.pgpass

import: touch/import

# --slim creates the planet_osm_rels table, and runs *much* longer (600 vs. 150 s.)

touch/import: $(DATADIR)/$(OSM_BASE) hikemap.lua hikemap.style
	osm2pgsql --multi-geometry --hstore --style hikemap.style \
		--tag-transform-script hikemap.lua --number-processes 8 \
	    --bbox 11.5,46.25,12,46.75 \
		--slim \
		--host $(PGHOST) --database $(PGDATABASE) --username $(PGUSER) $(DATADIR)/$(OSM_BASE)
	$(PSQL) -f $(OSM_CARTO)/indexes.sql
	touch touch/import

download:
	wget -N -P $(DATADIR) $(GEO_FABRIK)/$(OSM_DUMP)
	$(OSM_CARTO)/scripts/get-shapefiles.py -d $(DATADIR)

roads-diff:
	-diff -U 3 $(OSM_CARTO)/roads.mss roads.mss > roads.patch

roads.mss: $(OSM_CARTO)/roads.mss roads.patch
	cp $(OSM_CARTO)/roads.mss .
	patch < roads.patch

touch/hikemap.sql: hikemap.sql touch/import
	$(PSQL) -f $<
	touch $@

hikemap.xml: project.mml *.mss
	$(CARTO) $< > $@

xml: hikemap.xml touch/hikemap.sql

# url: http://hikemap.fritz.box/osm_tiles/{zoom}/{x}/{y}.png

renderd: xml
	rm -rf /var/lib/mod_tile/default
	renderd -f -c /usr/local/etc/renderd.conf

test: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.758,46.587,11.759,46.588 --scale=z16 hikemap.xml

test_val: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.7994,46.5629,11.7995,46.563 --scale=z16 hikemap.xml

test_ferrata: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.8254,46.5186,11.8255,46.5187 --scale=z16 hikemap.xml

test_ferrata2: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.7865,46.5152,11.7866,46.5153 --scale=z16 hikemap.xml
