#!/usr/bin/env python3

import argparse
import csv
import ipaddress
import json
import psycopg2
import socket
import sys

DIEM_PROTO = 'dns'
DIEM_PREFIX = '_diem'

def asn_to_id(asn):
    return str(asn) + '.' + 'asn'

def create_diem_id(objid, suffix):
    return f'{DIEM_PROTO}:{DIEM_PREFIX}.{objid}.{suffix}?CLASS=IN;TYPE=TXT'

def create_claims(row, suffix, organization):
    objid = asn_to_id(row[1])
    claims = {
            'diem_id': create_diem_id(objid, suffix),
            'diem_asset_type': 'digital',
            'diem_asset_id': row[1],
            'diem_asset_id_issuer': row[3],
            'diem_asset_id_type': 'asn',
            'diem_asset_desc': row[2],
            }
    return claims


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dbname', '-d',
                        type=str, default=None, action='store',
                        help='The name of the database into which ' + \
                                'data should be imported, if any.  ' + \
                                'Requires --dbtable.')
    parser.add_argument('--dbtable', '-t',
                        type=str, default='protected_location', action='store',
                        help='The name of the database table into which ' + \
                                'data should be imported, if any.  ' + \
                                'Requires --dbname.')
    parser.add_argument('--output_file', '-o',
                        type=argparse.FileType(mode='w'),
                        default=None, action='store',
                        help='The output file to which JWT claims ' + \
                                'should be output, line by line, if any.')
    parser.add_argument('input_file',
                        type=argparse.FileType(mode='r'),
                        default=None, action='store',
                        help='The input file containing the data to be ' + \
                                'processed.')
    parser.add_argument('organization',
                        type=str,
                        default=None, action='store')
    parser.add_argument('suffix',
                        type=str,
                        default=None, action='store')
    args = parser.parse_args(sys.argv[1:])

    if args.dbname is not None:
        conn = psycopg2.connect(database=args.dbname)
        curs = conn.cursor()
    else:
        conn = None
        curs = None

    mycsv = csv.reader(args.input_file)
    # consume headers
    headers = next(mycsv)
    for num, row in enumerate(mycsv):

        claims = create_claims(row, args.suffix, args.organization)
        if claims is None:
            continue

        row = [col.strip() for col in row]
        if args.output_file is not None:
            claims_json = json.dumps(claims)
            args.output_file.write(claims_json + '\n')

        if curs is not None:
            curs.execute('INSERT INTO ' + args.dbtable + ' ' + \
                    '(organization, desc_brief, diem_id, ' + \
                    'authority, asn) VALUES ' + \
                    '(%s, %s, %s, %s, %s)',
                         (args.organization,
                          row[2], claims['diem_id'], row[3], row[1]))

    if conn is not None:
        conn.commit()

if __name__ == '__main__':
    main()
