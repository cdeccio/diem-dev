#!/usr/bin/env python3

import argparse
import base64
import csv
import json
import math
import sys

import geopandas as gpd
import psycopg2
import shapely

EPSG_WGS84 = 'epsg:4326' # WGS 84
EPSG_ALBERS_EA = 'epsg:9822' # Albers equal area

SQ_METERS_PER_HECTARE = 10000

DIEM_PROTO = 'dns'
DIEM_PREFIX = '_diem'

def _extract_geometry(geo):
    '''Given geo, a geojson-like dict that is of type "FeatureCollection" and has
    only a single shape/geometry, extract the sole geometry object, and return
    it.  If geo is not of type "FeatureCollection", or if there is more than
    one geometry object in the features list, then just return the original
    geo.'''

    if geo.get('type', None) != 'FeatureCollection':
        return geo
    features = geo.get('features', [])
    if len(features) != 1:
        return geo
    mygeo = features[0].get('geometry', None)
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

def create_square(lat, lon, area):
    '''Given a latitude/longitude as the central point, create a circle with an
    area designated by area, then identify an "envelope" that bounds that
    circle.  Return the coordinates of that envelop.'''

    #Ref: https://gis.stackexchange.com/a/331382
    gdf = gpd.GeoDataFrame(geometry=[shapely.geometry.Point(lon, lat)])
    gdf.crs = EPSG_WGS84
    gdf = gdf.to_crs(EPSG_ALBERS_EA)
    area_sq_meters = area * SQ_METERS_PER_HECTARE
    r = math.sqrt(area_sq_meters/math.pi)
    gdf['geometry'] = gdf['geometry'].apply(lambda x: x.buffer(r).envelope)
    gdf = gdf.to_crs(EPSG_WGS84)
    return _extract_geometry(json.loads(gdf.to_json()))

def create_diem_id(row, suffix):
    return f'{DIEM_PROTO}://{DIEM_PREFIX}.%d.{suffix}' % (int(row[0]))

def create_claims(row, min_area, suffix):
    try:
        lat = float(row[8])
        lon = float(row[9])
    except ValueError:
        sys.stderr.write(f'Error: Problem with location for ID {row[0]}.\n')
        return None

    try:
        area = float(row[7])
    except ValueError:
        area = int(row[7])
    claims = {
            'diem_id': create_diem_id(row, suffix),
            'diem_asset_type': 'physical',
            'location': create_square(lat, lon, max(area, min_area))
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
    parser.add_argument('--min_area',
                        type=float,
                        default=1.0, action='store',
                        help='The minimum area for a location, ' + \
                                'in hectares.  Default: 1.0.')
    parser.add_argument('--output_file', '-o',
                        type=argparse.FileType(mode='w'),
                        default=None, action='store',
                        help='The output file to which JWT claims ' + \
                                'should be output, line by line, if any.')
    parser.add_argument('--input_format', '-f',
                        type=str,
                        default='ramsar_ris', action='store',
                        choices=('ramsar_ris',),
                        help='The format of the data to be inputted.' + \
                                'Currently, "ramsar_ris" is the only ' + \
                                'valid option.')
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

        claims = create_claims(row, args.min_area, args.suffix)
        if claims is None:
            continue

        row = [col.strip() for col in row]
        if args.output_file is not None:
            claims_json = json.dumps(claims)
            args.output_file.write(claims_json + '\n')

        if curs is not None:
            loc = claims['location']
            loc_postgis = _geojson_to_postgis(loc)
            if loc_postgis:
                curs.execute('INSERT INTO ' + args.dbtable + ' ' + \
                        '(organization, id, desc_brief, date_designated, ' + \
                             'date_updated, location) VALUES ' + \
                             '(%s, %s, %s, %s, %s, %s)',
                             (args.organization,
                              row[0], row[1], row[5] or None,
                              row[6] or None,
                              _geojson_to_postgis(claims['location'])))
            else:
                sys.stderr.write(f'Error: Problem with location for ID {row[0]}.\n')

    if conn is not None:
        conn.commit()

if __name__ == '__main__':
    main()
