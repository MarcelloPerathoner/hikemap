GEO_FABRIK  = https://download.geofabrik.de
OSM_DUMP    = europe/italy/nord-est-latest.osm.pbf
OSM_UPDATES = europe/italy/nord-est-updates/
OSM_BASE    = $(notdir $(OSM_DUMP))
OSM_CARTO   = ../openstreetmap-carto
SRTM        = ../srtm-stylesheets
DTM_TIFFS   := $(wildcard downloadService/downloadService/DTM-2p5m_*.tif)

# http://gis2.provinz.bz.it/geobrowser/?project=geobrowser_pro&view=geobrowser_pro_atlas-b&locale=de

OSM_SRS       = EPSG:3857     # The SRS used by OpenStreetMap
BZIT_SRS      = EPSG:25832    # ETRS89 / UTM zone 32N used by provinz.bz.it
WGS_SRS       = EPSG:4326     # WGS84

# the region we are interested in WGS coords
XMIN=11.5
YMIN=46.40
XMAX=12
YMAX=46.80
BBOX_OSM2PSQL = $(XMIN),$(YMIN),$(XMAX),$(YMAX)
BBOX_GDAL     = $(XMIN) $(YMIN) $(XMAX) $(YMAX)
BBOX_SRS      = $(WGS_SRS)

# from gdalinfo
XMIN_OSM=1280174.144
XMAX_OSM=1335833.890
YMIN_OSM=5844682.851
YMAX_OSM=5909489.864
BBOX_OSM=$(XMIN_OSM) $(YMIN_OSM) $(XMAX_OSM) $(YMAX_OSM)

PGHOST     = localhost
PGUSER     = osm
PGDATABASE = osm
PGPASSWORD := $(shell apg -a 1 -m 12 -n 1 -E ":'")

PSQL      = psql -d $(PGDATABASE)
SU_PSQL   = sudo -u postgres psql
CARTO     = ~/.npm-global/bin/carto
OGR2OGR   = ogr2ogr
OSM2PGSQL = osm2pgsql
GDALWARP  = /usr/bin/gdalwarp -multi -wo NUM_THREADS=ALL_CPUS -overwrite -of GTiff

DATADIR = $(CURDIR)/data

MSS := $(wilcard *.mss)

all: xml

prereq:
	sudo apt-get install apg osm2pgsql sed wget \
		fonts-noto-cjk fonts-noto-hinted fonts-noto-unhinted fonts-hanazono ttf-unifont
	sudo echo "d /run/renderd 1755 renderd_user renderd_user" > /etc/tmpfiles.d/renderd.conf

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

# convert to 16bit tiffs
%.tiff: %.tif
	gdal_translate -ot UInt16 $< /tmp/tmp.tif

# the DTM warped to EPSG:3857
# -tr 5 5 avoids artefacts
data/dtm-warped.tif: $(DTM_TIFFS)
	$(GDALWARP) -r lanczos -rcs -order 3 -tr 5 5 \
		-t_srs $(OSM_SRS) -te $(BBOX_GDAL) -te_srs $(BBOX_SRS) $^ /tmp/tmp.tif
	gdal_calc.py -A /tmp/tmp.tif --outfile=$@ --calc="A*(A>100)*(A<3500)" --NoDataValue=0 --overwrite

dem: hill-shade contour-lines touch/import_dem

hill-shade: data/hill-shade.tif

data/hill-shade.tif: data/dtm-warped.tif
	gdaldem hillshade $< $@

contour-lines: data/contour-lines-25.shp data/contour-lines-100.shp

# build contour lines and simplify them
data/contour-lines-100.shp: data/dtm-warped.tif
	gdal_contour -a ELEVATION $< /tmp/cont100.shp -i 100 -snodata 0
	$(OGR2OGR) $@ /tmp/cont100.shp -simplify 2.5

data/contour-lines-25.shp: data/dtm-warped.tif
	gdal_contour -a ELEVATION $< /tmp/cont025.shp -i  25 -snodata 0
	$(OGR2OGR) $@ /tmp/cont025.shp -simplify 2.5

# import into Postgres for altimetry
touch/import_dem: data/dtm-warped.tiff
	raster2pgsql -s $(OSM_SRS) -d -C -I -M -t 100x100 $^ public.raster_dtm | $(PSQL) -q
	touch touch/import_dem

# obsolete: get hill shades manually from http://geokatalog.buergernetz.bz.it/geokatalog/
data/hillshade.tif: downloadService/dtm/*.tif
	$(GDALWARP) -t_srs $(OSM_SRS) -te $(BBOX_GDAL) -te_srs $(BBOX_SRS) -dstalpha $^ $@

# obsolete: get ContourLines manually from http://geokatalog.buergernetz.bz.it/geokatalog/
data/contourlines.shp: downloadService/dataset/ContourLines_line.shp
	$(OGR2OGR) -spat $(BBOX_OSM) -spat_srs $(OSM_SRS) -s_srs $(BZIT_SRS) -t_srs $(OSM_SRS) \
		-clipdst $(BBOX_OSM) \
		$@ $<

# get HikingTrails manually from http://geokatalog.buergernetz.bz.it/geokatalog/
# use this as data layer in the OSM iD editor
data/hiking-trails.json: downloadService/dataset/HikingTrails_line.shp
	$(OGR2OGR) -spat $(BBOX_GDAL) -spat_srs $(BBOX_SRS) \
		-s_srs $(BZIT_SRS) -t_srs $(WGS_SRS) \
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
