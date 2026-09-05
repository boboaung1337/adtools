import base64
import hashlib
import sys

def md4(data):
    try: 
        return hashlib.new("md4", data).hexdigest()
    except ValueError:
        from Crypto.Hash import MD4
        return MD4.new(data).hexdigest()

if __name__ == "__main__":
    print("Enter base64 string (press Enter twice to finish):")
    lines = []
    while True:
        line = sys.stdin.readline().strip()
        if not line and lines:  # Empty line after content
            break
        if line:
            lines.append(line)
        else:
            # If first line is empty, wait for input
            continue
    
    data = ''.join(lines)
    if data:
        try:
            decoded = base64.b64decode(data)
            print(f"\nNTLM Hash: {md4(decoded)}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("No input provided")
