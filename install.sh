#!/usr/bin/env bash
set -e

echo "📦 Installing pipx apps from $(pwd)..."

for dir in */; do
    [[ "$dir" =~ ^\..* ]] && continue
    [[ ! -f "$dir/pyproject.toml" ]] && continue

    app="${dir%/}"
    echo "🔧 Installing $app..."

    pipx install "./$app" --force || {
        echo "❌ Failed to install $app"
        exit 1
    }
done

echo "✅ All pipx apps installed successfully."
