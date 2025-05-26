import subprocess
import re

def get_installed_kernels():
    result = subprocess.run(
        ["dpkg", "--list"], stdout=subprocess.PIPE, text=True, check=True
    )
    kernel_packages = []
    for line in result.stdout.splitlines():
        if re.search(r"linux-(image|headers|modules)(-extra)?-[\d]", line):
            parts = line.split()
            if parts and parts[0] == "ii":
                kernel_packages.append(parts[1])
    return kernel_packages

def get_current_kernel():
    return subprocess.check_output(["uname", "-r"], text=True).strip()

def extract_kernel_versions(packages):
    versions = set()
    for pkg in packages:
        match = re.search(r"-(\d+\.\d+\.\d+-\d+)", pkg)
        if match:
            versions.add(match.group(1))
    return sorted(versions, key=lambda v: list(map(int, re.findall(r'\d+', v))))

def remove_kernel(version):
    targets = [
        f"linux-image-{version}-generic",
        f"linux-headers-{version}",
        f"linux-headers-{version}-generic",
        f"linux-modules-{version}-generic",
        f"linux-modules-extra-{version}-generic",
        f"linux-tools-{version}",
    ]

    installed = get_installed_kernels()
    to_remove = [pkg for pkg in targets if pkg in installed]

    if to_remove:
        print(f"\n🔧 Removing kernel version {version}:")
        subprocess.run(["sudo", "apt", "remove", "-y"] + to_remove)
    else:
        print(f"\nℹ️  No packages found to remove for version {version}.")

def main():
    print("🔍 Detecting installed kernel packages...")
    current_kernel = get_current_kernel()
    current_version = current_kernel.split("-generic")[0]
    installed = get_installed_kernels()
    versions = extract_kernel_versions(installed)

    print(f"\n🟢 Currently running kernel: {current_kernel}")
    print(f"📦 Found kernel versions: {', '.join(versions)}")

    # Always keep the current and the latest installed version
    keep = {current_version}
    if versions:
        keep.add(versions[-1])

    print(f"\n✅ Keeping versions: {', '.join(sorted(keep))}")
    print("🗑️  Preparing to remove:")

    removed_any = False
    for version in versions:
        if version not in keep:
            print(f" - {version}")
            remove_kernel(version)
            removed_any = True

    if not removed_any:
        print("\n🎉 No old kernels to remove. System is already clean.")
