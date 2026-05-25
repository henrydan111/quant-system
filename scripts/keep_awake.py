import ctypes
import sys
import time
import argparse

# Windows API constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def prevent_sleep():
    """
    Prevents the computer from going to sleep or turning off the display.
    Only works on Windows.
    """
    if sys.platform == 'win32':
        # Prevent idle-to-sleep and display-off
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        print("Sleep prevention activated. The display and system will stay awake.")

def allow_sleep():
    """
    Restores normal sleep behavior.
    """
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        print("Sleep prevention deactivated. Normal sleep behavior restored.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prevent Windows from sleeping.")
    parser.add_argument("--hours", type=float, default=24, help="Hours to keep awake. Default is 24.")
    args = parser.parse_args()

    prevent_sleep()
    try:
        sleep_seconds = args.hours * 3600
        print(f"Keeping system awake for {args.hours} hours... Press Ctrl+C to stop early.")
        
        # Sleep in chunks to allow KeyboardInterrupt to be caught reasonably quickly
        for _ in range(int(sleep_seconds)):
            time.sleep(1)
            
        print("Time elapsed.")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        allow_sleep()
