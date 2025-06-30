#!/bin/bash

if [ "$1" = "" ]; then
	echo "Usage: $0 <dbname>" 1>&2
	exit 1
fi
DBNAME=$1

createdb $DBNAME
psql -c "CREATE TABLE protected_ip (organization VARCHAR(512),
         desc_brief VARCHAR(1024), diem_id VARCHAR(512),
         authority VARCHAR(512), net CIDR);" $DBNAME
psql -c "CREATE TABLE protected_asn (organization VARCHAR(512),
         desc_brief VARCHAR(1024), diem_id VARCHAR(512),
         authority VARCHAR(512), asn int);" $DBNAME
