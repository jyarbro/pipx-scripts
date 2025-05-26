# kernelcleaner

`kernelcleaner` is a simple command-line tool that removes old Linux kernel versions to help keep your system clean and reclaim disk space.

Built for use with [`pipx`](https://github.com/pypa/pipx), it safely keeps the currently running kernel and the most recently installed one, while offering clear output on what it's doing.

---

## 🔧 Features

- Detects and lists all installed kernel packages
- Keeps:
  - Your **currently running kernel**
  - The **newest available kernel**
- Removes all other outdated kernel packages using `apt`
- Provides clear, color-coded terminal output

---

## 🚀 Installation

```bash
pipx install ./kernelcleaner
