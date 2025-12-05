#!/usr/bin/env python3

import os
import sys
import subprocess
import tempfile
import time

def notify(title, message, timeout=2000):
    """Send desktop notification"""
    try:
        subprocess.run(["notify-send", title, message, "-t", str(timeout)],
                      check=False)
    except:
        pass

def is_recording():
    """Check if recording is in progress"""
    pid_file = "/tmp/whisper-dictate.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is still running
            os.kill(pid, 0)
            return True, pid, pid_file
        except (OSError, ValueError):
            # Process not running, clean up stale pid file
            os.remove(pid_file)
            return False, None, pid_file
    return False, None, "/tmp/whisper-dictate.pid"

def start_recording(pid_file, audio_file):
    """Start audio recording"""
    print("Recording... (run again to stop)")
    notify("Whisper Dictation", "Recording started. Run again to stop.")

    # Record from default microphone using parec piped to sox
    # parec captures from mic, sox converts to proper WAV format
    # Start in a new process group to safely kill it later
    cmd = f"parec --format=s16le --rate=16000 --channels=1 | sox -t raw -r 16000 -e signed -b 16 -c 1 - {audio_file}"
    proc = subprocess.Popen(cmd, shell=True, start_new_session=True)

    # Save PID
    with open(pid_file, 'w') as f:
        f.write(str(proc.pid))

    print(f"Recording PID: {proc.pid}")

def stop_recording_and_transcribe(pid, pid_file, model="base", language="en"):
    """Stop recording and transcribe with Whisper"""
    audio_file = "/tmp/whisper-dictate.wav"

    # Stop the recording process
    # Since we started with start_new_session=True, we can safely kill the session
    print("Stopping recording...")
    try:
        # Send SIGTERM to the process group to allow graceful shutdown
        os.killpg(pid, 15)  # SIGTERM to process group
        time.sleep(1.5)  # Give sox time to finalize the WAV file
    except:
        # Fallback to killing just the PID
        try:
            os.kill(pid, 15)
            time.sleep(1.5)
        except:
            pass

    # Clean up PID file
    if os.path.exists(pid_file):
        os.remove(pid_file)

    # Check if audio file was created
    if not os.path.exists(audio_file) or os.path.getsize(audio_file) < 1000:
        print("No audio recorded.")
        notify("Whisper Dictation", "No audio recorded.")
        return

    # Transcribe with Whisper
    print("Transcribing with Whisper...")
    notify("Whisper Dictation", "Transcribing...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run([
                "whisper", audio_file,
                "--model", model,
                "--language", language,
                "--task", "transcribe",
                "--output_format", "txt",
                "--output_dir", tmpdir,
                "--fp16", "False"
            ], capture_output=True, text=True)

            # Read transcribed text
            # Whisper creates a file named after the input file
            txt_file = os.path.join(tmpdir, os.path.basename(audio_file).replace('.wav', '.txt'))
            if os.path.exists(txt_file):
                with open(txt_file, 'r') as f:
                    text = f.read().strip()

                if text:
                    print(f"Typing: {text}")
                    notify("Whisper Dictation", "Typing text...")

                    # Wait a moment for window focus
                    time.sleep(0.3)

                    # Type the text using xdotool
                    subprocess.run(["xdotool", "type", "--delay", "10", text], check=True)

                    print("Done!")
                else:
                    print("No text transcribed.")
                    notify("Whisper Dictation", "No text transcribed.")
            else:
                print("Transcription failed.")
                notify("Whisper Dictation", "Transcription failed.")
    except Exception as e:
        print(f"Error during transcription: {e}")
        notify("Whisper Dictation", f"Error: {e}")
    finally:
        # Clean up audio file
        if os.path.exists(audio_file):
            os.remove(audio_file)

def main():
    # Parse arguments
    model = "medium"  # Default model
    language = "en"  # Default language

    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("Usage: dictate [MODEL] [LANGUAGE]")
            print("  MODEL: tiny, base, small, medium, large (default: base)")
            print("  LANGUAGE: language code (default: en)")
            print("\nRun once to start recording, run again to stop and transcribe.")
            sys.exit(0)
        model = sys.argv[1]

    if len(sys.argv) > 2:
        language = sys.argv[2]

    recording, pid, pid_file = is_recording()

    if recording:
        # Stop recording and transcribe
        stop_recording_and_transcribe(pid, pid_file, model, language)
    else:
        # Start recording
        audio_file = "/tmp/whisper-dictate.wav"
        start_recording(pid_file, audio_file)

if __name__ == "__main__":
    main()
