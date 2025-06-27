#!/bin/bash

if [ "$1" = "" ]; then
	echo "Usage: $0 <dbname>" 1>&2
	exit 1
fi
DBNAME=$1
DBTABLE=protected_area

createdb $DBNAME || exit 1;
psql -c 'CREATE EXTENSION postgis' $DBNAME || exit 1;
psql -c 'CREATE TABLE $DBTABLE (organization VARCHAR(512), id INT,
         desc_brief VARCHAR(1024), diem_id VARCHAR(512),
         date_designated DATE, date_updated DATE, location GEOMETRY);' $DBNAME
