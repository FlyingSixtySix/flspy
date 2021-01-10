# flspy

```
usage: fls.py [-h] [--encoding ENCODING] [--filter FILTER] [--filter-type {whitelist,blacklist}] [--domains DOMAINS] [--chunks CHUNKS] [--verbose] [--quiet] [input] [output]

Sorts all URLs found in the given input files into the relevant domain group files.

positional arguments:
  input                 input directory path
  output                output directory path

optional arguments:
  -h, --help            show this help message and exit
  --encoding ENCODING   input file encoding
  --filter FILTER       comma-separated file extensions to include or exclude
  --filter-type {whitelist,blacklist}
                        whether to use the filter as a whitelist or blacklist
  --domains DOMAINS, -d DOMAINS
                        domain list file path
  --chunks CHUNKS, -c CHUNKS
                        chunk size in bytes
  --verbose, -v         verbose output (hurts performance)
  --quiet, -q           no output

```

## Running

1. Configure `domains.txt` (default) or `domains.json` with the domains to group by
2. `python3 fls.py [OPTIONS]` (see above)

## Migrating from [file-link-sorter](https://github.com/FlyingSixtySix/file-link-sorter)

The only thing to migrate is the domain list. `flspy` supports both `.txt` domain input and JSON domain input.
The easiest way to migrate would be to copy this section out of the old `config.json` and paste it into `domains.json`:

```json
[
  "bandcamp.com",
  "docs.google.com",
  "drive.google.com",
  "..."
]
```

Note that we are NOT copying the `"domains": ` bit but rather the domain array `[ ... ]` itself.

The other way to migrate the domains list is by rewriting every line in `domains` per-line in `domains.txt`.
