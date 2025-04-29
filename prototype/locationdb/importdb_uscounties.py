#!/usr/bin/env python3

import argparse
import json
import sys

import psycopg2

DIEM_PROTO = 'dns'
DIEM_PREFIX = '_diem'

def _extract_geometry(geo):
    '''Given geo, a geojson-like dict that is of type "Feature", extract the
    geometry object, and return it.  If geo is not of type "Feature", then just
    return the original geo.'''

    if geo.get('type', None) != 'Feature':
        return geo
    mygeo = geo.get('geometry', None)
    if not mygeo:
        return geo
    return mygeo

def _geojson_to_postgis(geojson):
    '''Convert a geojson geometry object to a string suitable for PostGIS.'''

    if geojson['type'].lower() != 'polygon':
        return None

    coord_sets = []
    for l in geojson['coordinates']:
        coord_set = ', '.join([f'{p1} {p2}' for (p1, p2) in l])
        coord_sets.append(coord_set)
    coord_sets_str = '),('.join(coord_sets)
    return f'POLYGON(({coord_sets_str}))'

def create_diem_id(obj, suffix):
    return f'{DIEM_PROTO}:{DIEM_PREFIX}.%d.{suffix}?CLASS=IN;TYPE=TXT' % \
            (int(obj['coty_code'][0]))

HUNDRED_ACRE_MAPPING = {
        '16017': "Rabbit's House", # Bonner 16017
        '16053': "Pooh's House", # Jerome 16053
        '16069': "Tigger's House", # Nez Perce 16069
        '16057': "Piglet's House", # Latah 16057
        '16075': "Owl's House", # Payette 16075
        '16001': "Roo's House", # Ada 16001
        }

def create_claims(obj, suffix):
    claims = {
            'diem_id': create_diem_id(obj, suffix),
            'diem_asset_type': 'physical',
            'diem_asset_id': str(obj['coty_code'][0]),
            'diem_asset_id_issuer': 'us-counties',
            'diem_asset_desc': f"{obj['coty_name'][0]} County, {obj['ste_name'][0]}",
            'diem_location': _extract_geometry(obj['geo_shape'])
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
    parser.add_argument('--hun_acre_wood', action='store_const', const=True,
                        default=False,
                        help='Use contrived data 100-acre-wood.')
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

    blob = json.loads(args.input_file.read())
    for obj in blob:

        claims = create_claims(obj, args.suffix)
        if claims is None:
            continue

        if args.hun_acre_wood:
            if claims['diem_asset_id'] in HUNDRED_ACRE_MAPPING:
                claims['diem_asset_desc'] = HUNDRED_ACRE_MAPPING[claims['diem_asset_id']]
            else:
                continue

        if args.output_file is not None:
            claims_json = json.dumps(claims)
            args.output_file.write(claims_json + '\n')

        if curs is not None:
            loc = claims['diem_location']
            loc_postgis = _geojson_to_postgis(loc)
            if loc_postgis:
                curs.execute('INSERT INTO ' + args.dbtable + ' ' + \
                        '(organization, id, desc_brief, location) VALUES ' + \
                             '(%s, %s, %s, %s)', (args.organization,
                              int(obj['coty_code'][0]), claims['diem_asset_desc'],
                              _geojson_to_postgis(claims['diem_location'])))
            else:
                sys.stderr.write(f'Error: Problem with location for ID {claims["diem_asset_desc"]}.\n')

    if conn is not None:
        conn.commit()

if __name__ == '__main__':
    main()
