# WikiUpdate

A CLI tool to update MediaWiki installations with the latest Wikipedia dumps.

## Features

- 🔍 Automatically finds the latest completed Wikipedia dump
- 📦 Downloads and verifies Wikipedia dump files
- 🔄 Preserves revision history (adds new revisions, doesn't replace)
- ⚡ Optimized import process with progress tracking
- 🧹 Automatic cleanup of old dump files
- 💾 Smart caching (skips re-download if files exist)

## Installation

```bash
cd ~/Coding/pipx/wikiupdate
pipx install -e .
```

## Usage

Basic usage (check for and install updates):
```bash
wikiupdate
```

Force re-download even if files exist:
```bash
wikiupdate --force-download
```

## How It Works

1. **Check for Updates**: Queries wikimedia.org for the latest completed dump
2. **Download**: Downloads the multistream dump and index files
3. **Verify**: Checks MD5 checksums to ensure file integrity
4. **Import**: Streams the dump into MediaWiki (preserves old revisions)
5. **Rebuild**: Rebuilds search indexes and caches
6. **Cleanup**: Removes old dump files to save space

## Revision History

When you import a new dump, MediaWiki creates **new revisions** for each updated page. This means:

- Old versions are preserved (e.g., your 2023 import remains as revision 1)
- New versions are added (e.g., 2024 import becomes revision 2)
- You can view any historical version via "View history" on each page
- You can compare or revert to old versions at any time

## Requirements

- Python 3.10+
- MediaWiki running in Docker
- Sudo access for Docker commands
- Sufficient disk space (~100GB for English Wikipedia)

## Configuration

The tool is currently configured for:
- Wiki directory: `/mnt/das-storage/docker/mediawiki`
- Language: English Wikipedia (enwiki)
- Dump type: pages-articles-multistream

To change these, edit the constants in `wikiupdate/__main__.py`:
```python
WIKI_DIR = Path("/mnt/das-storage/docker/mediawiki")
WIKI_LANG = "enwiki"
DUMP_TYPE = "pages-articles-multistream"
```

## Time Estimates

- **Download**: 2-6 hours (depending on internet speed)
- **Import**: 4-12 hours (depending on CPU/disk speed)
- **Total**: 6-18 hours for complete update

The import process runs in the background and can be monitored via log files.

## Troubleshooting

**MediaWiki container not running:**
```bash
cd /mnt/das-storage/docker/mediawiki
sudo docker compose up -d
```

**Check import progress:**
```bash
tail -f /mnt/das-storage/docker/mediawiki/import_YYYYMMDD.log
```

**Disk space issues:**
The tool automatically cleans up old dumps, but you may need to manually remove files:
```bash
cd /mnt/das-storage/docker/mediawiki
rm enwiki-OLDDATE-*.xml* enwiki-OLDDATE-*.bz2
```

## License

MIT
