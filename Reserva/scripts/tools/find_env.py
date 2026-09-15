import os
import sys

def find_bad_env():
    for k, v in os.environ.items():
        try:
            v.encode('utf-8')
        except UnicodeEncodeError:
            print(f"Variable {k} has encoding issues (UnicodeEncodeError)")
        
        # Binary check
        raw_v = os.fsencode(v)
        if b'\xf3' in raw_v:
            print(f"Variable {k} contains byte 0xf3!")
            print(f"Value as bytes: {list(raw_v)}")

if __name__ == "__main__":
    find_bad_env()
