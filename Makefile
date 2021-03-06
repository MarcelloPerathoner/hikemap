# where are the dependencies installed?
OSM_CARTO   = ../openstreetmap-carto
SRTM        = ../srtm-stylesheets

DATADIR     = $(CURDIR)/data

# where do we get planet files, DTMs, etc.?
GEO_FABRIK_DUMP = https://download.geofabrik.de/europe/italy/nord-est-latest.osm.pbf
OSM_DUMP        = $(DATADIR)/nord-est-latest.osm.pbf
# OSM_UPDATES = europe/italy/nord-est-updates/

# download manually from geokatalog using GeoTiff in ETRS89.UTM32N
# download in 6 chunks, then use
# scripts/unzip_stupid_geokatalog_dtm_download_format.sh to unpack
DTM_TIFFS   := $(wildcard downloadService/dtm/DTM-2p5m_*.tif)

# the input database clipped to the region of interest
OSM_CLIPPED = $(DATADIR)/clipped.osm

# http://gis2.provinz.bz.it/geobrowser/?project=geobrowser_pro&view=geobrowser_pro_atlas-b&locale=de

SRS_OSM       = EPSG:3857     # The SRS used by OpenStreetMap
SRS_BZIT      = EPSG:25832    # ETRS89 / UTM zone 32N used by provinz.bz.it
SRS_WGS       = EPSG:4326     # WGS84

# DTM of South Tyrol
DTM_XMIN=10.36
DTM_XMAX=12.54
DTM_YMIN=46.18
DTM_YMAX=47.14

# the region we are interested in WGS coords
XMIN=10.36
XMAX=12.54
YMIN=46.18
YMAX=47.14
BBOX_WGS      = $(XMIN) $(YMIN) $(XMAX) $(YMAX)
BBOX_OSM2PSQL = $(XMIN),$(YMIN),$(XMAX),$(YMAX)

# the region we are interested in OSM coords (from gdalinfo)
XMIN_OSM=1153269.925
XMAX_OSM=1395944.925
YMIN_OSM=5809240.650
YMAX_OSM=5964955.650
BBOX_OSM=$(XMIN_OSM) $(YMIN_OSM) $(XMAX_OSM) $(YMAX_OSM)

PGHOST      = localhost
PGUSER      = osm

# the osm2pgsql schema (used by openstreetmap-carto)
# https://wiki.openstreetmap.org/wiki/Osm2pgsql/schema
PGDATABASE  = osm
PGPASSWORD  := $(shell apg -a 1 -m 32 -M ncl -n 1)

# we also import the pgsnapshot schema
# https://wiki.openstreetmap.org/wiki/Osmosis/Detailed_Usage_0.47#PostGIS_Tasks_.28Snapshot_Schema.29
SNAP_DIR     = /usr/share/doc/osmosis/examples
SNAP_DB      = osm
SNAP_SCHEMA  = snapshot

PSQL      = psql -h $(PGHOST) -U $(PGUSER)
PSQL_OSM  = $(PSQL) -d $(PGDATABASE)
PSQL_SNAP = $(PSQL) -d $(SNAP_DB) -c 'SET search_path TO $(SNAP_SCHEMA),public'

PSQL_SU   = sudo -u postgres psql
CARTO     = node_modules/carto/bin/carto
OGR2OGR   = ogr2ogr
OSM2PGSQL = osm2pgsql
GDALWARP  = /usr/bin/gdalwarp -multi -wo NUM_THREADS=ALL_CPUS -overwrite -of GTiff

OGR2_BASE = $(OGR2OGR) -spat_srs $(SRS_WGS) \
			-s_srs $(SRS_BZIT) -t_srs $(SRS_WGS) -f "GeoJSON" -simplify 1.0 \
			-lco "SIGNIFICANT_FIGURES=10" -dim XY

MSS := $(wilcard style/*.mss)

all: xml

psql:
	$(PSQL) -d $(PGDATABASE)

import: touch/import_dem touch/hikemap.sql

prereq:
	sudo apt-get install apg osmosis osm2pgsql sed wget \
		fonts-noto-cjk fonts-noto-hinted fonts-noto-unhinted fonts-hanazono ttf-unifont
	sudo pip3 install osmapi
	sudo echo "d /run/renderd 1755 renderd_user renderd_user" > /etc/tmpfiles.d/renderd.conf

clean_db:
	$(PSQL_SU) -c "DROP DATABASE IF EXISTS $(PGDATABASE)"
	$(PSQL_SU) -c "DROP ROLE IF EXISTS $(PGUSER)"
	sed -i.bak "/^$(PGHOST):\*:\*:$(PGUSER):/d" ~/.pgpass

create_db: clean_db
	# things to do as user postgres
	$(PSQL_SU) -c "CREATE ROLE $(PGUSER) LOGIN PASSWORD '$(PGPASSWORD)'"
	echo "$(PGHOST):*:*:$(PGUSER):$(PGPASSWORD)" >> ~/.pgpass
	$(PSQL_SU) -c "CREATE DATABASE $(PGDATABASE) OWNER $(PGUSER)"
	$(PSQL_SU) -c "ALTER DATABASE $(PGDATABASE) SET postgis.gdal_enabled_drivers TO 'GTiff PNG JPEG'"
	$(PSQL_SU) -c "ALTER DATABASE $(PGDATABASE) SET postgis.enable_outdb_rasters = True"
	$(PSQL_SU) -d $(PGDATABASE) -c "CREATE EXTENSION postgis; CREATE EXTENSION hstore"
	# Fix ERROR:  type "raster" does not exist
	$(PSQL_SU) -d $(PGDATABASE) < /usr/share/postgresql/12/contrib/postgis-3.0/rtpostgis.sql
	$(PSQL_SU) -d $(PGDATABASE) < /usr/share/postgresql/12/contrib/postgis-3.0/topology.sql

touch/hikemap.sql: hikemap.sql touch/osm2pgsql touch/osmosis
	$(PSQL_OSM) -f $<
	touch $@

# clip the planet file to the region of interest
$(OSM_CLIPPED): $(OSM_DUMP)
	osmosis --read-pbf-fast $(OSM_DUMP) workers=8 --log-progress \
		--bounding-box left=$(XMIN) right=$(XMAX) bottom=$(YMIN) top=$(YMAX) \
		completeRelations=yes cascadingRelations=yes \
		--write-xml $@

# load into postgres using the openstreetmap-carto database scheme.  this scheme
# is highly optimized for the mapnik renderer but no good for anything else.
touch/osm2pgsql: $(OSM_CLIPPED) hikemap.lua hikemap.style
	$(OSM2PGSQL) --multi-geometry --hstore --style hikemap.style \
		--tag-transform-script $(OSM_CARTO)/openstreetmap-carto.lua --number-processes 8 \
		--host $(PGHOST) --database $(PGDATABASE) --username $(PGUSER) $<
	$(PSQL_OSM) -f $(OSM_CARTO)/indexes.sql
	touch $@

# load into postgres using a sensible (osmosis snapshot) database scheme.  this
# scheme has all tables in a relational way
# See: https://wiki.openstreetmap.org/wiki/Osmosis/PostGIS_Setup
touch/osmosis: $(OSM_CLIPPED)
	mkdir -p pgimport
	$(PSQL) -d $(SNAP_DB) -c "DROP SCHEMA IF EXISTS $(SNAP_SCHEMA) CASCADE"
	$(PSQL) -d $(SNAP_DB) -c "CREATE SCHEMA IF NOT EXISTS $(SNAP_SCHEMA)"
	$(PSQL_SNAP) -f $(SNAP_DIR)/pgsnapshot_schema_0.6.sql
	$(PSQL_SNAP) -f $(SNAP_DIR)/pgsnapshot_schema_0.6_action.sql
	$(PSQL_SNAP) -f $(SNAP_DIR)/pgsnapshot_schema_0.6_bbox.sql
	$(PSQL_SNAP) -f $(SNAP_DIR)/pgsnapshot_schema_0.6_linestring.sql
	osmosis --read-xml $< --log-progress \
		--write-pgsql-dump pgimport enableBboxBuilder=yes enableLinestringBuilder=yes
	cd pgimport; $(PSQL_SNAP) -f $(SNAP_DIR)/pgsnapshot_load_0.6.sql; cd ..
	rm pgimport/*
	touch $@

download:
	curl -z $(OSM_DUMP) -o $(OSM_DUMP) $(GEO_FABRIK_DUMP)
	$(OSM_CARTO)/scripts/get-external-data.py

build-patch:
	-diff -U 3 $(OSM_CARTO)/project.mml     project.mml     > project.patch
	-diff -U 3 $(OSM_CARTO)/style/roads.mss style/roads.mss > roads.patch

project.mml: $(OSM_CARTO)/project.mml project.patch
	cp $(OSM_CARTO)/project.mml .
	patch < project.patch

# style/roads.mss: $(OSM_CARTO)/style/roads.mss roads.patch
#	cp $(OSM_CARTO)/style/roads.mss style/
#	patch < roads.patch

hikemap.xml: project.mml style/*.mss
	$(CARTO) $< > $@.tmp
	mv $@.tmp $@

# convert to 16bit tiffs
%.tiff: %.tif
	gdal_translate -ot UInt16 $< /tmp/tmp.tif

# stitch the DTM geotiffs
# and warp them to EPSG:3857
#   -tr 5 5 avoids artefacts
data/dtm-warped.tif: $(DTM_TIFFS)
	$(GDALWARP) -r lanczos -rcs -order 3 -tr 5 5 \
		-t_srs $(SRS_OSM) -te $(BBOX_WGS) -te_srs $(SRS_WGS) $^ /tmp/tmp.tif
	gdal_calc.py -A /tmp/tmp.tif --outfile=$@ --calc="A*(A>100)*(A<4000)" --NoDataValue=0 --overwrite

dem: hill-shade contour-lines import-dem

hill-shade: data/hill-shade.tif

contour-lines: data/contour-lines-25.shp data/contour-lines-100.shp

import-dem: touch/import_dem

data/hill-shade.tif: data/dtm-warped.tif
	gdaldem hillshade $< $@

# build contour lines and simplify them
data/contour-lines-100.shp: data/dtm-warped.tif
	gdal_contour -a ELEVATION $< /tmp/cont100.shp -i 100 -snodata 0
	$(OGR2OGR) $@ /tmp/cont100.shp -simplify 2.5

data/contour-lines-25.shp: data/dtm-warped.tif
	gdal_contour -a ELEVATION $< /tmp/cont025.shp -i  25 -snodata 0
	$(OGR2OGR) $@ /tmp/cont025.shp -simplify 2.5

# import into Postgres for altimetry
touch/import_dem: data/dtm-warped.tif
	raster2pgsql -s $(SRS_OSM) -d -C -I -M -e -t auto $^ public.raster_dtm | $(PSQL_OSM) -q
	touch $@

data: data/hiking-trails.geojson       			\
	data/hiking-trails-wipptal.geojson    		\
	data/hiking-trails-eisacktal.geojson  		\
	data/hiking-trails-pustertal.geojson    	\
	data/hiking-trails-salten-schlern.geojson	\
	data/hiking-trails-unterland.geojson    	\
	data/mtb-tours.json            		\
	data/bicycle-lanes.json        		\
	data/ski-pistes.json           		\
	data/landuse-plan.json

# get HikingTrails manually from http://geokatalog.buergernetz.bz.it/geokatalog/
# use this as data layer in JOSM
data/hiking-trails.geojson: downloadService/HikingTrails.geojson
	$(OGR2_BASE) -spat $(BBOX_WGS) -nlt LINESTRING $@ $<

data/hiking-trails-%.geojson: downloadService/HikingTrails.geojson data/%.extent
	$(RM) $@
	$(OGR2_BASE) -spat $(file < data/$*.extent) -nlt LINESTRING $@ $<

# write extent files with:
# scripts/check_routes_order.py -a 6536736 --write-areas-bbox data/unterland.extent

# get SkiPistes manually from http://geokatalog.buergernetz.bz.it/geokatalog/
# use this as data layer in JOSM
data/ski-pistes.json: downloadService/dataset/SkiPistes_polygon.shp
	$(OGR2_BASE) -spat $(BBOX_WGS) -nlt POLYGON $@ $<

# get LandUsePlan manually from http://geokatalog.buergernetz.bz.it/geokatalog/
# use this as data layer in JOSM
data/landuse-plan.json: downloadService/dataset/LandUsePlan_Lines_line.shp
	$(OGR2_BASE) -spat $(BBOX_WGS) -nlt LINESTRING $@ $<

data/mtb-tours.json: downloadService/dataset/MountainbikeTours_line.shp
	$(OGR2_BASE) -spat $(BBOX_WGS) -nlt LINESTRING $@ $<

data/bicycle-lanes.json: downloadService/dataset/BicycleLanes_line.shp
	$(OGR2_BASE) -spat $(BBOX_WGS) -nlt LINESTRING $@ $<

xml: hikemap.xml touch/hikemap.sql

# renderd for use as JOSM background imagery
# url: http://hikemap.fritz.box/osm_tiles/{zoom}/{x}/{y}.png
renderd: xml
	rm -rf /var/lib/mod_tile/default
	renderd -f -c ./renderd.conf

server: xml
	cd server ; make server

test: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.758,46.587,11.759,46.588 --scale=z16 hikemap.xml

test_val: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.7994,46.5629,11.7995,46.563 --scale=z16 hikemap.xml

test_ferrata: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.8254,46.5186,11.8255,46.5187 --scale=z16 hikemap.xml

test_ferrata2: xml
	./mapnik-render-image.py --size=2048x2048 -b 11.7865,46.5152,11.7866,46.5153 --scale=z16 hikemap.xml
