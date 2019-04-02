GEO_FABRIK  = https://download.geofabrik.de
OSM_DUMP    = europe/italy/nord-est-latest.osm.pbf
OSM_UPDATES = europe/italy/nord-est-updates/
OSM_BASE    = $(notdir $(OSM_DUMP))
OSM_CARTO   = ../openstreetmap-carto
SRTM         = ../srtm-stylesheets

# the region we are interested in SRS EPSG:4326
XMIN=11.5
YMIN=46.40
XMAX=12
YMAX=46.80
DEST_SRS      = EPSG:4326
BBOX_SRS      = EPSG:4326
BBOX_OSM2PSQL = $(XMIN),$(YMIN),$(XMAX),$(YMAX)
BBOX_OGR2OGR  = $(XMIN) $(YMIN) $(XMAX) $(YMAX)

PGHOST     = localhost
PGUSER     = osm
PGDATABASE = osm
PGPASSWORD := $(shell apg -a 1 -m 12 -n 1 -E ":'")

PSQL     = psql -d $(PGDATABASE)
SU_PSQL  = sudo -u postgres psql
CARTO    = ~/.npm-global/bin/carto
OGR2OGR  = ogr2ogr
OSM2PSQL = osm2psql

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
	$(OSM2PGSQL) --multi-geometry --hstore --style hikemap.style \
		--tag-transform-script hikemap.lua --number-processes 8 \
		--bbox $(BBOX_OSM2PSQL) \
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

data/hill-shade.tif: downloadService/dtm/*.tif
	/usr/bin/gdalwarp -multi -dstalpha -overwrite \
		-t_srs $(DEST_SRS) -te $(XMIN) $(YMIN) $(XMAX) $(YMAX) \
		$^ $@

# get ContourLines manually from http://geokatalog.buergernetz.bz.it/geokatalog/
data/contour-lines.shp: downloadService/dataset/ContourLines_line.shp
	$(OGR2OGR) -spat $(XMIN) $(YMIN) $(XMAX) $(YMAX) -spat_srs $(BBOX_SRS) \
		-s_srs "EPSG:25832" -t_srs $(DEST_SRS) \
	    -clipdst $(XMIN) $(YMIN) $(XMAX) $(YMAX) \
		$@ $<

# get HikingTrails manually from http://geokatalog.buergernetz.bz.it/geokatalog/
# use this as data layer in the OSM iD editor
data/hiking-trails.json: downloadService/dataset/HikingTrails_line.shp
	$(OGR2OGR) -spat $(XMIN) $(YMIN) $(XMAX) $(YMAX) -spat_srs $(BBOX_SRS) \
		-s_srs "EPSG:25832" -t_srs $(DEST_SRS) \
		-f "GeoJSON" $@ $<

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
