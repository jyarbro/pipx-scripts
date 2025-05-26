# fixsteamcompatibility

Moves Steam Proton `compatdata/` prefixes to a native filesystem (e.g., ext4)
and replaces them with symlinks. Useful for fixing prefix issues on non-native
filesystems like NTFS or exFAT.

## Usage

```bash
fixsteamcompatibility
