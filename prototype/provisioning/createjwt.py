#!/usr/bin/env python3

import argparse
import base64
import json
import socket
import sys
import urllib

import dns.name, dns.exception, dns.resolver

from dns_update import parse_tsig_key_file, send_update

MAX_TXT_STRING_LEN = 255

def jwt_base64decode(s):
    rem = len(s) % 4
    if rem == 0:
        pass
    elif rem == 2:
        s += '=='
    elif rem == 3:
        s += '='
    else: # rem == 1
        raise ValueError(f'Incorrect length of base64-encoded string: {s}')
    return base64.urlsafe_b64decode(s).decode('utf-8')

def jwt_base64encode(s):
    return base64.urlsafe_b64encode(s.encode('utf-8')).\
            rstrip(b'=').decode('utf-8')

UNSECURED_HEADER = { 'alg': 'none' }
UNSECURED_HEADER_ENCODED = \
        jwt_base64encode(json.dumps(UNSECURED_HEADER, separators=(',',':')))

def jwt_encode(claims, hdr=None):
    if hdr is None:
        hdr_enc = UNSECURED_HEADER_ENCODED
    else:
        hdr_enc = jwt_base64encode(json.dumps(hdr, separators=(',',':')))
    claims_enc = jwt_base64encode(json.dumps(claims, separators=(',',':')))

    return f'{hdr_enc}.{claims_enc}'

def jwt_decode(s):
    hdr_enc, claims_enc = s.split('.', maxsplit=1)

    hdr = json.loads(jwt_base64decode(hdr_enc))
    claims = json.loads(jwt_base64decode(claims_enc))

    return hdr, claims

def get_addr_for_name(n):
    try:
        s = socket.getaddrinfo(n, 53)
        return s[0][4][0]
    except socket.gaierror:
        return None

def get_mname_for_zone(n):
    try:
        a = dns.resolver.resolve(n, 'SOA')
    except dns.exception.DNSException:
        return None
    return a.rrset[0].mname.to_text()

def upload_jwt(jwt, url, ttl, server, zone, subzone_labels, keyring, alg):
    assert zone is not None or subzone_labels is not None

    url2 = urllib.parse.urlparse(url)

    if url2.scheme != 'dns':
        raise ValueError(f'Incorrect scheme: {url2.scheme}\n')

    pairs = dict([p.split('=', maxsplit=1) for p in url2.query.split(';')])
    if (pairs['CLASS'], pairs['TYPE']) != ('IN', 'TXT'):
        raise ValueError(f'Incorrect class/type: {url2.query}\n')

    name = dns.name.from_text(url2.path)
    if zone is not None:
        if not name.is_subdomain(zone):
            raise ValueError(f'Name out of zone: {url2.path}\n')

    else:
        zone = dns.name.Name(name[subzone_labels:])

    if server is None:
        server = get_mname_for_zone(zone)
        if server is None:
            raise ValueError(f'No MNAME for zone {zone}\n')
    server = get_addr_for_name(server)

    jwt_parts = []
    jwt_rem = jwt
    while len(jwt_rem) > MAX_TXT_STRING_LEN:
        jwt_parts.append(jwt_rem[:MAX_TXT_STRING_LEN])
        jwt_rem = jwt_rem[MAX_TXT_STRING_LEN:]
    if jwt_rem:
        jwt_parts.append(jwt_rem)

    jwt_rdata = '"' + '" "'.join(jwt_parts) + '"'
    try:
        send_update(zone, name, ttl, pairs['TYPE'],
                    jwt_rdata, server, keyring=keyring, alg=alg, tcp=True)
    except AssertionError as e:
        sys.stderr.write(f'Error: {str(e)}\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update_dns', default=False,
                        action='store_const', const=True,
                        help='Upload JWT to DNS using dynamic DNS update.')
    parser.add_argument('--subzone_labels', type=int, default=None,
                        help='The number of subdomain labels that should ' + \
                                'be stripped from a domain name to form ' + \
                                'the zone for that domain name. This is ' + \
                                'required if --update_dns is specified ' + \
                                'and --zone is not specified. ')
    parser.add_argument('--zone', type=dns.name.from_text, default=None,
                        action='store',
                        help='Zone within which records should be ' + \
                                'sent via DNS updates.  This is ' + \
                                'required if --update_dns is specified ' + \
                                'and --subzone_labels is not specified.')
    parser.add_argument('--ttl', type=int, default=3600, action='store',
                        help='Default TTL for records uploaded with ' + \
                                'DNS updates.  The default is 3600.')
    parser.add_argument('--server', type=str, default=None, action='store',
                        help='Server to which DNS updates should be sent. ' + \
                                'If not specified, the server is looked ' + \
                                'using the MNAME field of the SOA record ' + \
                                'of the zone.')
    parser.add_argument('--tsig-key-file',
                        type=argparse.FileType(mode='r', encoding='utf-8'),
                        default=None, action='store',
                        help='File containing TSIG key for securing ' + \
                                'DNS updates.  The default is to not ' + \
                                'use TSIG.')
    parser.add_argument('--output_file',
                        type=argparse.FileType(mode='w', encoding='utf-8'),
                        default=None, action='store',
                        help='The file to which the JWTs should be ' + \
                                'written, if any.')
    parser.add_argument('input_file',
                        type=argparse.FileType(mode='r', encoding='utf-8'),
                        default=None, action='store',
                        help='The file containing the claims to be ' + \
                                'processed, one claim per line, ' + \
                                'JSON-encoded.')
    args = parser.parse_args(sys.argv[1:])

    general_server = None
    if args.server:
        general_server = get_addr_for_name(args.server)
        if general_server is None:
            sys.stderr.write('Invalid server name: %s\n' % args.server)
            sys.exit(1)

    # retrieve the key and algorithm, if any
    if args.tsig_key_file is not None:
        keyring, alg = parse_tsig_key_file(args.tsig_key_file)
    else:
        keyring, alg = None, None

    zone = None
    subzone_labels = None
    if args.update_dns:
        if (args.zone is not None and args.subzone_labels is not None) or \
                (args.zone is None and args.subzone_labels is None):
            sys.stderr.write('Exactly one of --zone or --subzone_labels ' + \
                    'must be used with --update_dns.\n')
            sys.exit(1)

    for line in args.input_file:
        line = line.strip()
        try:
            claims = json.loads(line)
        except ValueError:
            sys.stderr.write('Invalid JSON: ' + line + '\n')
            continue

        jwt = jwt_encode(claims)
        if args.output_file is not None:
            args.output_file.write(f'{jwt}\n')

        if args.update_dns:
            upload_jwt(jwt, claims['diem_id'], args.ttl, args.server,
                       args.zone, args.subzone_labels, keyring, alg)

if __name__ == '__main__':
    main()
