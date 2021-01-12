#!/usr/bin/env python
import argparse
import json
import math
import os
import re
import time
import typing
from urllib.parse import urlparse


argparser = argparse.ArgumentParser(
    description='Sorts all URLs found in the given input files into the relevant domain group files.')
argparser.add_argument('input', help='input directory path', nargs='?', default='input')
argparser.add_argument('output', help='output directory path', nargs='?', default='output')
argparser.add_argument('--encoding', help='input file encoding', default='utf-8')
argparser.add_argument('--filter', help='comma-separated file extensions to include or exclude', default='')
argparser.add_argument('--filter-type', help='whether to use the filter as a whitelist or blacklist',
                       choices=['whitelist', 'blacklist'], default='blacklist')
argparser.add_argument('--domains', '-d', help='domain list file path', default='domains.txt')
argparser.add_argument('--chunks', '-c', help='chunk size in bytes', default=4096)
argparser.add_argument('--unescape-slashes', '-u', help='replace slash escapes with slashes', action='store_true',
                       default=True)
argparser.add_argument('--collapse-subdomains', '-s', help='collapse subdomains into their root domain',
                       action='store_true', default=False)
argparser.add_argument('--verbose', '-v', help='verbose output (hurts performance)', action='count', default=0)
argparser.add_argument('--quiet', '-q', help='no output', action='store_true', default=False)
args = argparser.parse_args()

encoding = args.encoding
extension_filter = args.filter.split(',')
args.chunks = int(args.chunks)


def get_domain_list():
    """
    Parses the domain list file either as JSON or split by line depending on file extension.
    :return: The parsed domain list.
    """
    with open(args.domains) as file:
        if args.domains.endswith('json'):
            return json.loads(file.read())
        else:
            return [line.strip() for line in file.readlines() if line.strip() != '']


def walk_paths(path):
    """
    :param path: The root directory to walk.
    :return: A list of absolute paths to files found within any child of the root path.
    """
    output = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if args.filter_type == 'blacklist' and os.path.splitext(file)[1] not in extension_filter \
                    or args.filter_type == 'whitelist' and os.path.splitext(file)[1] in extension_filter:
                output.append(os.path.join(root, file))
    return output


url_regex = re.compile(r'(?:https?:\\?/\\?/|www\.)[\w\d.]+(?::[\d]{1,5})?(?:\\?/[\w\d=#&\-?.:/!%@_~]+)+')
domains = {domain_name: [] for domain_name in get_domain_list()}
domains['unknown'] = []

input_paths = sorted(walk_paths(args.input))


def get_file_size(file):
    """
    Gets the size of the file by seeking to the end and getting the position.
    :param file: The file handle.
    :return: The size of the file in bytes.
    """
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    return file_size


def process_file(input_path, domain_handles):
    """
    Reads the given file in chunks and writes URLs to the domain category or unknown if none apply.
    :param input_path: The file path.
    :param domain_handles: The domain file handles.
    """
    global domains

    with open(input_path, 'r', encoding=encoding) as file:
        file_size = get_file_size(file)
        # This is only a section of the last chunk with the last match to the end of the chunk.
        last_chunk_with_last_match = None

        # Iterate over the file for however many chunks we use.
        for n in range(math.ceil(file_size / args.chunks)):
            chunk = file.read(args.chunks)

            matches = url_regex.findall(chunk)
            spans = [m.span() for m in url_regex.finditer(chunk)]

            # We have to check for span length in case there are no matches in this chunk.
            if len(spans) > 0:
                # If the last match's span end is or exceeds the chunk length (i.e. 4096 bytes), remove it.
                if spans[-1][1] >= len(chunk):
                    matches.pop()
                    spans.pop()

            # Double-check the length just in case we removed the only match.
            if len(spans) > 0:
                # Get a slice of the chunk up to the start of the first URL match (right before the http).
                chunk_up_to_first_match = chunk[:spans[0][0]]
                # If the last chunk's final slice was set and there is nothing to combine in this chunk (like a link
                # ending right on the chunk border)...
                if last_chunk_with_last_match is not None and len(chunk_up_to_first_match.strip()) > 0:
                    # Combine the two chunk slices. This will give us something like the following, where [] indicates
                    # URL matches, {} indicates the combined section, and | indicates the chunk border:
                    # abcdefg[https://link.tld/blahblahblah]{hijklmno|pqrstuvw}[https://link.tld/blahblahblah]xyz
                    combined = last_chunk_with_last_match + chunk_up_to_first_match
                    # Look for links from the start of the last match in the previous chunk to before the first match
                    # in the current chunk.
                    found_combined = url_regex.findall(combined)
                    # Because we're including the start of the last link match from the previous chunk, we might
                    # accidentally find two links, so only use the last one.
                    matches.insert(0, found_combined[-1])

                # Set the first half of the combined chunk slices.
                last_chunk_with_last_match = chunk[spans[-1][0]:]

            for match in matches:
                if args.unescape_slashes:
                    match = match.replace('\\/', '/')
                parsed_url = urlparse(match)
                domain_name = parsed_url.netloc.lstrip('www.')

                if args.collapse_subdomains:
                    import tldextract
                    extracted = tldextract.extract(match)
                    domain_name = extracted.domain + '.' + extracted.suffix

                if domain_name in domains:
                    domains[domain_name].append(match)
                else:
                    domains['unknown'].append(match)

    # domains: {
    #   'domain.tld': ['https://domain.tld/foo', 'http://domain.tld/bar', 'https://subdomain.domain.tld/baz'],
    #   'example.com': ['https://example.com/?params=work&too!foo#bar.baz']
    # }
    for domain_group, grouped_domains in domains.items():
        if args.verbose > 0:
            if len(grouped_domains) > 0:
                print(f'{domain_group}: {len(grouped_domains)} domains')
        for domain in grouped_domains:
            # If a file handle hasn't been opened for the domain, open and assign it.
            if domain_handles[domain_group] is None:
                # This should be reworked in the event more output types are added.
                handle_path = os.path.join(args.output, domain_group + '.txt')
                if args.verbose > 0:
                    print(f'Opening file handle for output {handle_path}...')
                domain_handles[domain_group] = open(handle_path, 'a+', encoding=encoding)
            domain_handles[domain_group].write(domain + '\n')
        # If the grouped domains aren't cleared, this can lead to output leaks!
        # I had a 207 GB output .txt from 774 MB worth of input files during testing!
        grouped_domains.clear()


def main():
    # Take note of the start time to calculate the final processing time.
    t0 = time.time()
    opened = 0

    # Create the output directory if it doesn't exist.
    if args.verbose > 0:
        print(f'Creating output directory \'{args.output}\' if it doesn\'t exist...')
    os.makedirs(args.output, exist_ok=True)

    # Map all the domains' output/*.txt files to None. File handles will be initialized on first use.
    domain_handles = {}
    for domain in domains:
        domain_handles[domain] = None

    if not args.quiet:
        print(f'Processing {len(input_paths)} files...')

    # Process every file found in the input directory.
    for input_path in input_paths:
        opened += 1
        if args.verbose > 0:
            print(f'{opened}/{len(input_paths)}:', input_path)
        process_file(input_path, domain_handles)

    # Close every domain file handle where applicable.
    for domain, handle in domain_handles.items():
        if handle is not None:
            handle: typing.IO
            handle.flush()
            handle.close()

    # Get the execution time after processing.
    t1 = time.time()

    if not args.quiet:
        print(f'Processed {len(input_paths)} files in {"{:.3f}".format(t1 - t0)} seconds')


if __name__ == '__main__':
    main()
