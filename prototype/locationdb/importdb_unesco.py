#!/usr/bin/env python3

import argparse
import base64
import csv
import json
import math
import sys
import urllib
import xml.dom.minidom

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

def create_diem_id(objid, suffix):
    return f'{DIEM_PROTO}:{DIEM_PREFIX}.{objid}.{suffix}?CLASS=IN;TYPE=TXT'

def create_claims(node, min_area, suffix, organization):
    try:
        lat = float(node.getElementsByTagName('geo:lat')[0].childNodes[0].nodeValue)
        lon = float(node.getElementsByTagName('geo:long')[0].childNodes[0].nodeValue)
    except (ValueError, IndexError):
        sys.stderr.write(f'Error: Problem with location for node {node}.\n')
        return None

    title = node.getElementsByTagName('title')[0].childNodes[0].nodeValue
    link = node.getElementsByTagName('link')[0].childNodes[0].nodeValue
    description = node.getElementsByTagName('description')[0].childNodes[0].nodeValue

    url = urllib.parse.urlparse(link)
    objid = url.path.split('/')[-1]

    claims = {
            'diem_id': create_diem_id(objid, suffix),
            'diem_asset_type': 'physical',
            'diem_asset_id': objid,
            'diem_asset_id_issuer': organization,
            'diem_asset_desc': title,
            'diem_location': create_square(lat, lon, min_area)
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

    dom = xml.dom.minidom.parseString(args.input_file.read())
    channel = dom.documentElement.getElementsByTagName('channel')[0]
    items = channel.getElementsByTagName('item')
    for item in items:
        claims = create_claims(item, args.min_area, args.suffix, args.organization)

        if claims is None:
            continue

        if args.output_file is not None:
            claims_json = json.dumps(claims)
            args.output_file.write(claims_json + '\n')

        if curs is not None:
            loc = claims['diem_location']
            diem_id = claims['diem_id']
            loc_postgis = _geojson_to_postgis(loc)
            if loc_postgis:
                curs.execute('INSERT INTO ' + args.dbtable + ' ' + \
                        '(organization, diem_id, id, desc_brief, ' + \
                             'date_designated, date_updated, location) ' + \
                             'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                             (args.organization, diem_id,
                              claims['diem_asset_id'], claims['diem_asset_desc'],
                              None, None,
                              _geojson_to_postgis(claims['diem_location'])))
            else:
                sys.stderr.write(f'Error: Problem with location for ID.\n')

    if conn is not None:
        conn.commit()

if __name__ == '__main__':
    main()
