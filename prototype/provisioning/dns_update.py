#!/usr/bin/env python3

import argparse
import re
import socket
import sys

import dns.name
import dns.query
import dns.rcode
import dns.rdatatype
import dns.tsigkeyring
import dns.update

TSIG_KEY_RE = re.compile(r'key\s+"([^"]+)"')
TSIG_ALG_RE = re.compile(r'algorithm\s+([^;\s]+)')
TSIG_SECRET_RE = re.compile(r'secret\s+"([^"]+)"')

class UpdateError(Exception):
    pass

def parse_tsig_key_file(file):
    key = None
    alg = None
    secret = None
    for line in file:
        line = line.strip()
        m = TSIG_KEY_RE.search(line)
        if m is not None:
            key = m.group(1)
        m = TSIG_ALG_RE.search(line)
        if m is not None:
            alg = m.group(1)
        m = TSIG_SECRET_RE.search(line)
        if m is not None:
            secret = m.group(1)
    keyring = dns.tsigkeyring.from_text({ key: secret })
    return keyring, alg

def send_update(zone, name, ttl, rdtype, contents,
                server, keyring=None, alg=None):
    # create the update message
    msg = dns.update.Update(zone, keyring=keyring, keyalgorithm=alg)
    # specify to add a record with the given contents and TTL at the given name
    msg.add(name, ttl, rdtype, contents)
    # send the update
    response = dns.query.tcp(msg, server)
    if response.rcode() != dns.rcode.NOERROR:
        raise UpdateError('updated failed with rcode %s' % \
                dns.rcode.to_text(response.rcode()))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tsig-key-file',
                        type=argparse.FileType(mode='r', encoding='utf-8'),
                        default=None)
    parser.add_argument('--ttl', type=int, default=3600)
    parser.add_argument('zone', type=dns.name.from_text)
    parser.add_argument('name', type=dns.name.from_text)
    parser.add_argument('type', type=dns.rdatatype.from_text)
    parser.add_argument('contents', type=str)
    parser.add_argument('server', type=str)
    args = parser.parse_args(sys.argv[1:])

    s = socket.getaddrinfo(args.server, 53)
    server = s[0][4][0]

    # retrieve the key and algorithm, if any
    if args.tsig_key_file is not None:
        keyring, alg = parse_tsig_key_file(args.tsig_key_file)
    else:
        keyring, alg = None, None

    send_update(args.zone, args.name, args.ttl, args.type,
                args.contents, server, keyring=keyring, alg=alg)

if __name__ == '__main__':
    main()
