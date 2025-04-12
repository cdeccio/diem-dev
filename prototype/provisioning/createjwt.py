#!/usr/bin/env python3

import argparse
import base64
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file',
                        type=argparse.FileType(mode='br'),
                        default=None, action='store',
                        help='The input file containing the data to be ' + \
                                'processed.')
    args = parser.parse_args(sys.argv[1:])

    for line in args.input_file:

        line = line.strip()
        try:
            claims = json.loads(line)
        except ValueError:
            sys.stderr.write('Invalid JSON: ' + line + '\n')
            continue

        unsecured_header = b'{"alg":"none"}'
        encoded_header = base64.urlsafe_b64encode(unsecured_header).\
                rstrip(b'=').decode('utf-8')
        encoded_claims = base64.urlsafe_b64encode(line).\
                rstrip(b'=').decode('utf-8')

        val = f'{encoded_header}.{encoded_claims}'

        print(len(val))


if __name__ == '__main__':
    main()
