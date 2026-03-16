import sys
import os

try:
    import data
    print(f"data package file: {data.__file__}")
    print(f"data package path: {getattr(data, '__path__', 'No Path')}")
    import data.historical_activity
    print("Successfully imported data.historical_activity")
except Exception as e:
    print(f"Error during import: {e}")

print(f"CWD contents: {os.listdir('.')}")
if os.path.exists('data'):
    print(f"data directory contents: {os.listdir('data')}")
