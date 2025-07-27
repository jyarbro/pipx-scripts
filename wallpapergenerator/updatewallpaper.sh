#!/bin/bash
# Only run wallpaper generator if session is unlocked and active
SESSION=$(loginctl | awk '/tty/ {print $1}')
STATUS=$(loginctl show-session "$SESSION" -p LockedHint -p IdleHint)
if echo "$STATUS" | grep -q 'LockedHint=no' && echo "$STATUS" | grep -q 'IdleHint=no'; then
    wallpapergenerator "a serene mountain landscape at sunset"
fi
