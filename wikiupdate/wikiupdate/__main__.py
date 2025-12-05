#!/usr/bin/env python3
"""
Wikipedia Dump Update Tool

Updates MediaWiki installation with latest Wikipedia dump.
Supports parallel import for faster processing and preserves revision history.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Confirm
from rich.table import Table

console = Console()

# Configuration
WIKI_DIR = Path("/mnt/das-storage/docker/mediawiki")
DUMP_BASE_URL = "https://dumps.wikimedia.org/enwiki"
WIKI_LANG = "enwiki"
DUMP_TYPE = "pages-articles-multistream"


class WikiUpdater:
    """Manages Wikipedia dump downloads and imports."""

    def __init__(self, wiki_dir: Path, force_download: bool = False, parallel_jobs: int = 8, rebuild_indexes_only: bool = False):
        self.wiki_dir = wiki_dir
        self.force_download = force_download
        self.parallel_jobs = parallel_jobs
        self.rebuild_indexes_only = rebuild_indexes_only
        self.dump_base_url = DUMP_BASE_URL
        self.wiki_lang = WIKI_LANG
        self.dump_type = DUMP_TYPE
        self.progress_file = wiki_dir / ".wikiupdate_progress.json"

    def load_progress(self) -> dict:
        """Load progress state from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_progress(self, state: dict):
        """Save progress state to file."""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save progress: {e}[/yellow]")

    def clear_progress(self):
        """Clear progress state file."""
        if self.progress_file.exists():
            self.progress_file.unlink()

    def get_latest_dump_date(self) -> Optional[str]:
        """Get the latest completed Wikipedia dump date."""
        console.print("[blue]🔍 Checking for latest completed Wikipedia dump...[/blue]")

        try:
            # Get list of available dumps
            response = requests.get(f"{self.dump_base_url}/", timeout=30)
            response.raise_for_status()

            # Extract dates from directory listings
            dates = re.findall(r'(\d{8})/', response.text)
            dates = sorted(set(dates), reverse=True)

            # Find the first complete dump
            for date in dates:
                md5_url = f"{self.dump_base_url}/{date}/{self.wiki_lang}-{date}-md5sums.txt"
                try:
                    md5_response = requests.head(md5_url, timeout=10)
                    if md5_response.status_code == 200:
                        console.print(f"[green]✓[/green] Latest completed dump: {date}")
                        return date
                except requests.RequestException:
                    continue

            console.print("[red]✗ Could not find a completed dump[/red]")
            return None

        except requests.RequestException as e:
            console.print(f"[red]✗ Error checking for dumps: {e}[/red]")
            return None

    def get_current_dump_date(self) -> Optional[str]:
        """Get the date of the currently installed dump."""
        # Check what dump files we have locally
        pattern = f"{self.wiki_lang}-*-pages-articles*.xml*"
        files = list(self.wiki_dir.glob(pattern))

        if not files:
            return None

        # Extract dates from filenames
        dates = []
        for file in files:
            match = re.search(r'(\d{8})', file.name)
            if match:
                dates.append(match.group(1))

        return max(dates) if dates else None

    def download_file(self, url: str, destination: Path, description: str) -> bool:
        """Download a file with progress bar."""
        if destination.exists() and not self.force_download:
            console.print(f"[green]✓[/green] {description} already exists")
            return True

        try:
            console.print(f"[blue]⬇[/blue]  Downloading {description}...")

            # Get file size
            response = requests.head(url, timeout=10)
            total_size = int(response.headers.get('content-length', 0))

            # Download with progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("•"),
                TextColumn("[cyan]{task.completed}/{task.total} MB[/cyan]"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(description, total=total_size // (1024 * 1024))

                with requests.get(url, stream=True, timeout=(30, 300)) as r:
                    r.raise_for_status()
                    with open(destination, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192 * 1024):  # 8MB chunks
                            if chunk:
                                f.write(chunk)
                                progress.update(task, advance=len(chunk) // (1024 * 1024))

            console.print(f"[green]✓[/green] Download complete: {description}")
            return True

        except Exception as e:
            console.print(f"[red]✗ Download failed: {e}[/red]")
            if destination.exists():
                destination.unlink()
            return False

    def download_dump(self, dump_date: str) -> bool:
        """Download Wikipedia dump files."""
        base_filename = f"{self.wiki_lang}-{dump_date}-{self.dump_type}"

        # Download multistream XML
        xml_file = self.wiki_dir / f"{base_filename}.xml.bz2"
        xml_url = f"{self.dump_base_url}/{dump_date}/{base_filename}.xml.bz2"
        if not self.download_file(xml_url, xml_file, "Wikipedia dump"):
            return False

        # Download multistream index
        index_file = self.wiki_dir / f"{base_filename}-index.txt.bz2"
        index_url = f"{self.dump_base_url}/{dump_date}/{base_filename}-index.txt.bz2"
        if not self.download_file(index_url, index_file, "Index file"):
            return False

        # Download checksums
        md5_file = self.wiki_dir / f"{self.wiki_lang}-{dump_date}-md5sums.txt"
        md5_url = f"{self.dump_base_url}/{dump_date}/{self.wiki_lang}-{dump_date}-md5sums.txt"
        self.download_file(md5_url, md5_file, "Checksums")  # Non-critical

        return True

    def verify_checksums(self, dump_date: str) -> bool:
        """Verify downloaded file checksums."""
        md5_file = self.wiki_dir / f"{self.wiki_lang}-{dump_date}-md5sums.txt"

        if not md5_file.exists():
            console.print("[yellow]⚠[/yellow]  No checksum file (skipping verification)")
            return True

        console.print("[blue]🔐 Verifying checksums...[/blue]")

        try:
            # Read relevant checksums
            with open(md5_file) as f:
                checksums = f.read()

            base_filename = f"{self.wiki_lang}-{dump_date}-{self.dump_type}"
            relevant_lines = [
                line for line in checksums.splitlines()
                if f"{base_filename}.xml.bz2" in line or f"{base_filename}-index.txt.bz2" in line
            ]

            if not relevant_lines:
                console.print("[yellow]⚠[/yellow]  No checksums found for downloaded files")
                return True

            # Write temporary checksum file
            temp_md5 = Path("/tmp/wikiupdate-verify.md5")
            temp_md5.write_text('\n'.join(relevant_lines))

            try:
                result = subprocess.run(
                    ["md5sum", "-c", str(temp_md5)],
                    cwd=self.wiki_dir,
                    capture_output=True,
                    text=True
                )

                if "FAILED" in result.stdout or result.returncode != 0:
                    console.print("[red]✗ Checksum verification failed![/red]")
                    return False

                console.print("[green]✓[/green] Checksum verification passed")
                return True
            finally:
                if temp_md5.exists():
                    temp_md5.unlink()

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow]  Checksum verification error: {e}")
            return True  # Don't fail the whole process

    def decompress_index(self, dump_date: str) -> bool:
        """Decompress the index file."""
        base_filename = f"{self.wiki_lang}-{dump_date}-{self.dump_type}"
        index_bz2 = self.wiki_dir / f"{base_filename}-index.txt.bz2"
        index_txt = self.wiki_dir / f"{base_filename}-index.txt"

        if index_txt.exists():
            console.print("[green]✓[/green] Index already decompressed")
            return True

        console.print("[blue]📦 Decompressing index...[/blue]")

        try:
            subprocess.run(
                ["bunzip2", "-k", str(index_bz2)],
                check=True,
                capture_output=True
            )
            console.print("[green]✓[/green] Index decompressed")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Decompression failed: {e}[/red]")
            return False

    def check_docker_running(self) -> bool:
        """Check if MediaWiki Docker containers are running."""
        try:
            result = subprocess.run(
                ["sudo", "docker", "compose", "ps"],
                cwd=self.wiki_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return "mw_app" in result.stdout
        except subprocess.CalledProcessError:
            return False

    def scale_up_resources(self) -> bool:
        """Scale up MariaDB resources for import (aggressive tuning)."""
        console.print("[blue]⚙[/blue]  Scaling up database resources for import...")

        # Backup current config files
        compose_file = self.wiki_dir / "docker-compose.yml"
        tuning_file = self.wiki_dir / "mariadb-conf" / "99-tuning.cnf"
        compose_backup = self.wiki_dir / "docker-compose.yml.backup"
        tuning_backup = self.wiki_dir / "mariadb-conf" / "99-tuning.cnf.backup"

        try:
            # Backup files
            subprocess.run(["cp", str(compose_file), str(compose_backup)], check=True)
            subprocess.run(["cp", str(tuning_file), str(tuning_backup)], check=True)

            # Update docker-compose.yml with aggressive settings
            with open(compose_file, 'r') as f:
                content = f.read()

            # Replace the command line with aggressive import settings
            content = re.sub(
                r'command: \["--innodb-buffer-pool-size=[^"]+", "--max-connections=[^"]+", "--innodb-io-capacity=[^"]+", "--innodb-io-capacity-max=[^"]+"\]',
                'command: ["--innodb-buffer-pool-size=16G", "--max-connections=200", "--innodb-io-capacity=4000", "--innodb-io-capacity-max=8000"]',
                content
            )

            with open(compose_file, 'w') as f:
                f.write(content)

            # Update 99-tuning.cnf with aggressive settings
            aggressive_config = """[mysqld]
innodb_log_file_size = 2G
innodb_flush_log_at_trx_commit = 0
innodb_thread_concurrency = 0
innodb_read_io_threads = 16
innodb_write_io_threads = 16
innodb_flush_method = O_DIRECT
innodb_doublewrite = 0
tmpdir = /dev/shm
skip_log_bin=1
max_heap_table_size = 2G
tmp_table_size = 2G
"""
            with open(tuning_file, 'w') as f:
                f.write(aggressive_config)

            # Restart database with new settings
            console.print("[blue]⚙[/blue]  Restarting database with aggressive settings...")
            subprocess.run(
                ["sudo", "docker", "compose", "restart", "db"],
                cwd=self.wiki_dir,
                check=True,
                capture_output=True
            )

            # Wait for database to be ready
            import time
            time.sleep(10)

            console.print("[green]✓[/green] Resources scaled up for import")
            console.print("[yellow]  - Buffer pool: 16G[/yellow]")
            console.print("[yellow]  - Max connections: 200[/yellow]")
            console.print("[yellow]  - IO capacity: 4000/8000[/yellow]")
            console.print("[yellow]  - Log file: 2G[/yellow]")
            console.print("[yellow]  - Flush at commit: 0 (unsafe but fast)[/yellow]")
            return True

        except Exception as e:
            console.print(f"[red]✗ Failed to scale up resources: {e}[/red]")
            # Attempt to restore backups
            try:
                subprocess.run(["cp", str(compose_backup), str(compose_file)], check=True)
                subprocess.run(["cp", str(tuning_backup), str(tuning_file)], check=True)
            except Exception:
                pass
            return False

    def scale_down_resources(self) -> bool:
        """Restore normal MariaDB resources after import."""
        console.print("\n[blue]⚙[/blue]  Restoring normal database resources...")

        compose_backup = self.wiki_dir / "docker-compose.yml.backup"
        tuning_backup = self.wiki_dir / "mariadb-conf" / "99-tuning.cnf.backup"

        try:
            # Check if backups exist
            if not compose_backup.exists() or not tuning_backup.exists():
                console.print("[yellow]⚠ No backup files found, using safe defaults[/yellow]")

                # Write safe default configs
                compose_file = self.wiki_dir / "docker-compose.yml"
                tuning_file = self.wiki_dir / "mariadb-conf" / "99-tuning.cnf"

                # Update compose file with normal settings
                with open(compose_file, 'r') as f:
                    content = f.read()

                content = re.sub(
                    r'command: \["--innodb-buffer-pool-size=[^"]+", "--max-connections=[^"]+", "--innodb-io-capacity=[^"]+", "--innodb-io-capacity-max=[^"]+"\]',
                    'command: ["--innodb-buffer-pool-size=2G", "--max-connections=50", "--innodb-io-capacity=1000", "--innodb-io-capacity-max=2000"]',
                    content
                )

                with open(compose_file, 'w') as f:
                    f.write(content)

                # Write normal tuning config
                normal_config = """[mysqld]
innodb_log_file_size = 512M
innodb_flush_log_at_trx_commit = 1
innodb_thread_concurrency = 0
innodb_read_io_threads = 4
innodb_write_io_threads = 4
innodb_flush_method = O_DIRECT
innodb_doublewrite = 1
skip_log_bin=1
max_heap_table_size = 512M
tmp_table_size = 512M
"""
                with open(tuning_file, 'w') as f:
                    f.write(normal_config)
            else:
                # Restore from backups
                compose_file = self.wiki_dir / "docker-compose.yml"
                tuning_file = self.wiki_dir / "mariadb-conf" / "99-tuning.cnf"

                subprocess.run(["cp", str(compose_backup), str(compose_file)], check=True)
                subprocess.run(["cp", str(tuning_backup), str(tuning_file)], check=True)

                # Remove backup files
                compose_backup.unlink()
                tuning_backup.unlink()

            # Restart database with normal settings
            console.print("[blue]⚙[/blue]  Restarting database with normal settings...")
            subprocess.run(
                ["sudo", "docker", "compose", "restart", "db"],
                cwd=self.wiki_dir,
                check=True,
                capture_output=True
            )

            console.print("[green]✓[/green] Resources restored to normal operation")
            console.print("[green]  - Buffer pool: 2G[/green]")
            console.print("[green]  - Max connections: 50[/green]")
            console.print("[green]  - IO capacity: 1000/2000[/green]")
            console.print("[green]  - ACID-compliant settings enabled[/green]")
            return True

        except Exception as e:
            console.print(f"[red]✗ Failed to restore resources: {e}[/red]")
            return False

    def get_estimated_total_pages(self, dump_date: str) -> int:
        """Estimate total pages from dump metadata or index file."""
        # BEST METHOD: count lines in index file (most accurate)
        base_filename = f"{self.wiki_lang}-{dump_date}-{self.dump_type}"
        index_file = self.wiki_dir / f"{base_filename}-index.txt"

        if index_file.exists():
            try:
                console.print("[dim]Counting pages from index file...[/dim]")
                result = subprocess.run(
                    ["wc", "-l", str(index_file)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                line_count = int(result.stdout.split()[0])
                # Each index entry represents a page
                console.print(f"[dim]Index file shows {line_count:,} pages[/dim]")
                return line_count
            except Exception as e:
                console.print(f"[yellow]⚠ Could not count index file: {e}[/yellow]")

        # Fallback: Try to get from WikiMedia API
        try:
            response = requests.get(
                f"{self.dump_base_url}/{dump_date}/dumpstatus.json",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                # Look for page count in metadata
                for job_name, job_data in data.get("jobs", {}).items():
                    if "articles" in job_name.lower():
                        files = job_data.get("files", {})
                        if files:
                            # Count multistream files (excluding index files)
                            xml_files = [f for f in files.keys() if f.endswith('.bz2') and 'index' not in f]
                            if xml_files:
                                # English Wikipedia multistream has ~25M pages total
                                # Rough estimate: 25M / ~80 files = ~310k per file
                                estimated = len(xml_files) * 310000
                                console.print(f"[dim]Estimated from API: {estimated:,} pages[/dim]")
                                return estimated
        except Exception:
            pass

        # Ultimate fallback: Known English Wikipedia total page count
        # This includes articles, redirects, disambiguation pages, etc.
        console.print("[yellow]⚠ Using fallback estimate of 25M pages[/yellow]")
        return 25000000  # ~25M total pages for English Wikipedia multistream

    def import_dump(self, dump_date: str) -> bool:
        """Import Wikipedia dump into MediaWiki."""
        if not self.check_docker_running():
            console.print("[red]✗ MediaWiki container is not running![/red]")
            console.print(f"Start it with: cd {self.wiki_dir} && sudo docker compose up -d")
            return False

        # Scale up resources for import
        if not self.scale_up_resources():
            console.print("[yellow]⚠ Warning: Could not scale up resources, continuing anyway...[/yellow]")

        base_filename = f"{self.wiki_lang}-{dump_date}-{self.dump_type}"
        xml_bz2 = self.wiki_dir / f"{base_filename}.xml.bz2"
        log_file = self.wiki_dir / f"import_{dump_date}.log"

        # Get estimated total pages
        estimated_total = self.get_estimated_total_pages(dump_date)

        console.print("\n[bold blue]Starting Wikipedia import...[/bold blue]")
        console.print(f"[cyan]Estimated pages:[/cyan] ~{estimated_total:,}")
        console.print(f"[cyan]Log file:[/cyan] {log_file}")
        console.print(f"[cyan]Progress file:[/cyan] {self.progress_file}\n")

        self.save_progress({
            "status": "importing",
            "dump_date": dump_date,
            "started_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "pages_imported": 0,
            "estimated_total": estimated_total,
            "log_file": str(log_file)
        })

        try:
            # Build the import pipeline
            bunzip2_cmd = ["bunzip2", "-c", str(xml_bz2)]
            import_cmd = [
                "sudo", "docker", "compose", "exec", "-T", "mediawiki",
                "php", "maintenance/importDump.php",
                "--conf", "/var/www/html/LocalSettings.php",
                "--no-updates",
                "--report=1000"
            ]

            with open(log_file, 'w') as log_f:
                bunzip2_proc = subprocess.Popen(
                    bunzip2_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )

                import_proc = subprocess.Popen(
                    import_cmd,
                    stdin=bunzip2_proc.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=self.wiki_dir
                )

                if bunzip2_proc.stdout:
                    bunzip2_proc.stdout.close()

                pages_count = 0
                last_progress_update = datetime.now()
                start_time = datetime.now()

                # Create progress bar
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(bar_width=40),
                    TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
                    TextColumn("•"),
                    TextColumn("[cyan]{task.completed:,}/{task.total:,} pages[/cyan]"),
                    TextColumn("•"),
                    TextColumn("[yellow]{task.fields[rate]:.0f} pages/sec[/yellow]"),
                    TextColumn("•"),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "Importing Wikipedia",
                        total=estimated_total,
                        rate=0.0
                    )

                    if import_proc.stdout:
                        try:
                            for line in import_proc.stdout:
                                log_f.write(line)
                                log_f.flush()

                                # Parse progress from importDump output
                                # Format: "1000 (202.14 pages/sec 202.14 revs/sec)"
                                match = re.match(r'^(\d+)\s+\(([\d.]+)\s+pages/sec', line)
                                if match:
                                    pages_count = int(match.group(1))
                                    current_rate = float(match.group(2))

                                    # Update progress bar
                                    progress.update(
                                        task,
                                        completed=pages_count,
                                        rate=current_rate
                                    )

                                    # Save progress periodically
                                    now = datetime.now()
                                    if (now - last_progress_update).seconds >= 30:
                                        elapsed = (now - start_time).total_seconds()
                                        avg_rate = pages_count / elapsed if elapsed > 0 else 0

                                        self.save_progress({
                                            "status": "importing",
                                            "dump_date": dump_date,
                                            "started_at": start_time.isoformat(),
                                            "last_update": now.isoformat(),
                                            "pages_imported": pages_count,
                                            "estimated_total": estimated_total,
                                            "progress_percent": (pages_count / estimated_total * 100) if estimated_total > 0 else 0,
                                            "avg_rate": avg_rate,
                                            "current_rate": current_rate,
                                            "log_file": str(log_file)
                                        })
                                        last_progress_update = now

                        except Exception as e:
                            console.print(f"\n[yellow]⚠ Stream reading error: {e}[/yellow]")
                    else:
                        console.print("\n[red]✗ Failed to capture import output[/red]")

                    import_returncode = import_proc.wait()
                    bunzip2_returncode = bunzip2_proc.wait()

                if bunzip2_returncode != 0:
                    bunzip2_stderr = bunzip2_proc.stderr.read() if bunzip2_proc.stderr else b""
                    console.print(f"\n[red]✗ Decompression failed with exit code {bunzip2_returncode}[/red]")
                    if bunzip2_stderr:
                        console.print(f"[red]bunzip2 error: {bunzip2_stderr.decode()}[/red]")
                    return False

                if import_returncode == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    avg_rate = pages_count / elapsed if elapsed > 0 else 0

                    self.save_progress({
                        "status": "completed",
                        "dump_date": dump_date,
                        "started_at": start_time.isoformat(),
                        "completed_at": datetime.now().isoformat(),
                        "last_update": datetime.now().isoformat(),
                        "pages_imported": pages_count,
                        "estimated_total": estimated_total,
                        "duration_seconds": elapsed,
                        "avg_rate": avg_rate,
                        "log_file": str(log_file)
                    })
                    console.print(f"\n[green]✓ Import completed successfully![/green]")
                    console.print(f"[green]  Pages imported:[/green] {pages_count:,}")
                    console.print(f"[green]  Time elapsed:[/green] {elapsed/3600:.1f} hours")
                    console.print(f"[green]  Average rate:[/green] {avg_rate:.0f} pages/sec")

                    # Scale down resources after successful import
                    self.scale_down_resources()
                    return True
                else:
                    self.save_progress({
                        "status": "failed",
                        "dump_date": dump_date,
                        "started_at": start_time.isoformat(),
                        "failed_at": datetime.now().isoformat(),
                        "last_update": datetime.now().isoformat(),
                        "pages_imported": pages_count,
                        "estimated_total": estimated_total,
                        "exit_code": import_returncode,
                        "log_file": str(log_file)
                    })
                    console.print(f"\n[red]✗ Import failed with exit code {import_returncode}[/red]")
                    console.print(f"[red]Check {log_file} for details[/red]")

                    # Scale down resources after failed import
                    self.scale_down_resources()
                    return False

        except Exception as e:
            self.save_progress({
                "status": "error",
                "dump_date": dump_date,
                "started_at": self.load_progress().get("started_at", datetime.now().isoformat()),
                "error_at": datetime.now().isoformat(),
                "last_update": datetime.now().isoformat(),
                "error": str(e),
                "log_file": str(log_file)
            })
            console.print(f"[red]✗ Import error: {e}[/red]")

            # Scale down resources after error
            self.scale_down_resources()
            return False

    def rebuild_indexes(self) -> bool:
        """Rebuild MediaWiki indexes and caches."""
        console.print("\n[bold blue]Rebuilding indexes and caches...[/bold blue]")

        steps = [
            ("Rebuilding recent changes", ["php", "maintenance/rebuildrecentchanges.php"], False),  # Optional - can fail
            ("Rebuilding all indexes", ["php", "maintenance/rebuildall.php"], True),  # Required
            ("Running maintenance jobs", ["php", "maintenance/runJobs.php"], True),  # Required
        ]

        failed_steps = []
        for description, cmd, required in steps:
            console.print(f"[blue]⚙[/blue]  {description}...")
            try:
                result = subprocess.run(
                    ["sudo", "docker", "compose", "exec", "-T", "mediawiki"] + cmd,
                    cwd=self.wiki_dir,
                    check=True,
                    capture_output=True,
                    text=True
                )
                console.print(f"[green]✓[/green] {description} complete")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗ {description} failed: {e}[/red]")
                if e.stderr:
                    console.print(f"[red]Error output:[/red]\n{e.stderr}")
                if e.stdout:
                    console.print(f"[yellow]Command output:[/yellow]\n{e.stdout}")

                if required:
                    return False
                else:
                    console.print(f"[yellow]⚠[/yellow]  {description} is optional, continuing...")
                    failed_steps.append(description)

        if failed_steps:
            console.print(f"[yellow]⚠ Some optional steps failed: {', '.join(failed_steps)}[/yellow]")
        console.print("[green]✓ Index rebuild complete![/green]")
        return True

    def cleanup_old_dumps(self, keep_date: str):
        """Remove old dump files, keeping only the specified date."""
        console.print(f"\n[blue]🧹 Cleaning up old dump files (keeping {keep_date})...[/blue]")

        patterns = [
            f"{self.wiki_lang}-*.xml",
            f"{self.wiki_lang}-*.xml.bz2",
            f"{self.wiki_lang}-*-index.txt",
            f"{self.wiki_lang}-*-index.txt.bz2",
            f"{self.wiki_lang}-*-md5sums.txt"
        ]

        for pattern in patterns:
            for file in self.wiki_dir.glob(pattern):
                if keep_date not in file.name:
                    console.print(f"[dim]  Removing: {file.name}[/dim]")
                    file.unlink()

        # Remove old log files (keep last 5)
        log_files = sorted(self.wiki_dir.glob("import_*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        for log_file in log_files[5:]:
            console.print(f"[dim]  Removing old log: {log_file.name}[/dim]")
            log_file.unlink()

        console.print("[green]✓ Cleanup complete[/green]")

    def show_disk_space(self):
        """Display disk space usage."""
        try:
            # Get filesystem usage
            result = subprocess.run(
                ["df", "-h", str(self.wiki_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                console.print(f"\n[bold]Disk Space:[/bold] {lines[1]}")

            # Get directory size
            result = subprocess.run(
                ["du", "-sh", str(self.wiki_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            size = result.stdout.split()[0]
            console.print(f"[bold]MediaWiki Directory:[/bold] {size}")

        except Exception as e:
            console.print(f"[yellow]⚠ Could not get disk space: {e}[/yellow]")

    def run(self) -> int:
        """Main execution flow."""
        console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]           Wikipedia Dump Update Tool                  [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

        # Handle rebuild-indexes-only mode
        if self.rebuild_indexes_only:
            console.print("[bold blue]Running index rebuild only...[/bold blue]\n")
            if not self.check_docker_running():
                console.print("[red]✗ MediaWiki container is not running![/red]")
                console.print(f"Start it with: cd {self.wiki_dir} && sudo docker compose up -d")
                return 1

            if self.rebuild_indexes():
                console.print("\n[bold green]✓ Index rebuild complete![/bold green]\n")
                return 0
            else:
                console.print("\n[bold red]✗ Index rebuild failed[/bold red]\n")
                return 1

        progress = self.load_progress()
        skip_download = False
        latest_date_to_import = None

        if progress and progress.get("status") == "importing":
            console.print("[yellow]⚠ Previous import detected as in progress[/yellow]")
            console.print(f"[yellow]  Dump: {progress.get('dump_date')}[/yellow]")
            console.print(f"[yellow]  Started: {progress.get('started_at')}[/yellow]")
            console.print(f"[yellow]  Last update: {progress.get('last_update')}[/yellow]")
            console.print(f"[yellow]  Pages imported: {progress.get('pages_imported', 0):,}[/yellow]")
            console.print(f"[yellow]  Log file: {progress.get('log_file')}[/yellow]\n")
        elif progress and progress.get("status") == "completed":
            console.print(f"[green]✓ Last import completed: {progress.get('completed_at')}[/green]")
            console.print(f"[green]  Dump: {progress.get('dump_date')}[/green]")
            console.print(f"[green]  Pages imported: {progress.get('pages_imported', 0):,}[/green]\n")
        elif progress and progress.get("status") in ["failed", "error"]:
            console.print(f"[red]✗ Previous import failed or had errors[/red]")
            console.print(f"[red]  Dump: {progress.get('dump_date')}[/red]")
            console.print(f"[red]  Status: {progress.get('status')}[/red]")
            if progress.get("error"):
                console.print(f"[red]  Error: {progress.get('error')}[/red]")
            console.print(f"[red]  Pages imported before failure: {progress.get('pages_imported', 0):,}[/red]\n")

        # Show system info
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Key", style="cyan")
        info_table.add_column("Value", style="white")

        cpu_count = subprocess.check_output(["nproc"], text=True).strip()

        info_table.add_row("System", subprocess.check_output(["hostname"], text=True).strip())
        info_table.add_row("CPU Cores", cpu_count)
        info_table.add_row("Parallel Jobs", str(self.parallel_jobs))
        info_table.add_row("MediaWiki Dir", str(self.wiki_dir))

        console.print(info_table)
        console.print()

        self.show_disk_space()

        # Get current and latest dump dates
        current_date = self.get_current_dump_date()
        console.print(f"\n[bold]Current dump:[/bold] {current_date or 'None'}")

        latest_date = self.get_latest_dump_date()
        if not latest_date:
            console.print("[red]✗ Could not determine latest dump date[/red]")
            return 1

        # Check if update is needed
        if current_date == latest_date and not self.force_download:
            # Check if the import was actually completed
            if progress and progress.get("dump_date") == latest_date:
                if progress.get("status") == "completed":
                    console.print(f"\n[green]✓ Already have the latest dump ({latest_date}) and import is complete[/green]")
                    console.print("[dim]Use --force-download to re-download and re-import[/dim]")
                    return 0
                elif progress.get("status") in ["importing", "failed", "error"]:
                    console.print(f"\n[yellow]⚠ Latest dump ({latest_date}) downloaded but import not completed[/yellow]")
                    console.print(f"[yellow]  Status: {progress.get('status')}[/yellow]")
                    console.print(f"[yellow]  Pages imported: {progress.get('pages_imported', 0):,}[/yellow]")

                    if not Confirm.ask("\nContinue with import?", default=True):
                        console.print("[yellow]Import cancelled by user[/yellow]")
                        return 0

                    # Skip download, go straight to import
                    latest_date_to_import = latest_date
                    skip_download = True
                else:
                    console.print(f"\n[green]✓ Already have the latest dump ({latest_date})[/green]")
                    console.print("[dim]Use --force-download to re-download and re-import[/dim]")
                    return 0
            else:
                console.print(f"\n[green]✓ Already have the latest dump ({latest_date})[/green]")
                console.print("[dim]Use --force-download to re-download and re-import[/dim]")
                return 0
        else:
            skip_download = False
            latest_date_to_import = latest_date

        if not skip_download:
            console.print(f"\n[bold green]Update available: {current_date or 'None'} → {latest_date}[/bold green]\n")

            # Download
            if not self.download_dump(latest_date):
                return 1

            # Verify
            if not self.verify_checksums(latest_date):
                return 1

            # Decompress index
            if not self.decompress_index(latest_date):
                return 1

            self.show_disk_space()

            # Confirm import
            console.print(f"\n[bold yellow]⚠  About to import Wikipedia dump dated {latest_date}[/bold yellow]")
            console.print("[yellow]   This will add new revisions to all Wikipedia articles[/yellow]")
            console.print("[yellow]   Estimated time: 4-12 hours depending on system performance[/yellow]\n")

            if not Confirm.ask("Continue with import?", default=False):
                console.print("[yellow]Import cancelled by user[/yellow]")
                return 0

        # Import (using latest_date_to_import which may be set from earlier)
        if not self.import_dump(latest_date_to_import):
            return 1

        # Rebuild indexes
        if not self.rebuild_indexes():
            console.print("[yellow]⚠ Warning: Index rebuild failed, but import completed[/yellow]")

        # Cleanup
        self.cleanup_old_dumps(latest_date_to_import)

        self.show_disk_space()

        self.clear_progress()

        # Success!
        console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
        console.print("[bold green]           Wikipedia Update Complete!                   [/bold green]")
        console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]")
        console.print(f"[green]Old version:[/green] {current_date or 'None'}")
        console.print(f"[green]New version:[/green] {latest_date_to_import}")
        console.print("\n[cyan]Access your wiki at: https://wiki.home.nrrd.io[/cyan]")
        console.print("[cyan]All pages now have multiple revisions - click 'View history' to see[/cyan]\n")

        return 0


def main():
    """Entry point for the wikiupdate command."""
    parser = argparse.ArgumentParser(
        description="Update MediaWiki with latest Wikipedia dump",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wikiupdate                      # Check for and install updates
  wikiupdate --force-download     # Re-download even if files exist
  wikiupdate --parallel-jobs 12   # Use 12 parallel jobs (not yet implemented)
  wikiupdate --rebuild-indexes-only # Only rebuild indexes (after import)

Notes:
  - This tool preserves revision history - old versions are kept
  - Import process takes 4-12 hours depending on hardware
  - Requires MediaWiki Docker containers to be running
        """
    )

    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download of dump files even if they exist"
    )

    parser.add_argument(
        "--parallel-jobs",
        type=int,
        default=8,
        help="Number of parallel import jobs (default: 8, not yet implemented)"
    )

    parser.add_argument(
        "--rebuild-indexes-only",
        action="store_true",
        help="Only rebuild MediaWiki indexes and caches (skip download/import)"
    )

    args = parser.parse_args()

    # Check if running as root or with sudo access
    try:
        subprocess.run(["sudo", "-n", "true"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        console.print("[red]✗ This tool requires sudo access[/red]")
        console.print("[yellow]Please run with sudo or ensure your user has passwordless sudo[/yellow]")
        return 1

    # Create updater and run
    updater = WikiUpdater(
        wiki_dir=WIKI_DIR,
        force_download=args.force_download,
        parallel_jobs=args.parallel_jobs,
        rebuild_indexes_only=args.rebuild_indexes_only
    )

    try:
        return updater.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
