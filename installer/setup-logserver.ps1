# Asterism setup log tap - a tiny localhost JSONP server so the browser
# welcome page can watch the HIDDEN bootstrap run, line by line.
#
# A file:// page cannot fetch() http and cannot read sibling files, but
# it CAN load an http <script> tag - so we serve the progress log
# wrapped as __asterismLog([...]) and the page polls by injecting a
# script every second. Raw TcpListener (not HttpListener) so no admin
# and no URL-ACL reservation is needed - the same socket bind the
# engine itself does. Self-exits the moment the real console (8642) is
# up, or after a safety timeout. PowerShell 5.1, ASCII only.

param(
    [string]$LogPath,
    [int]$Port = 8641,
    [int]$EnginePort = 8642
)
$ErrorActionPreference = 'SilentlyContinue'

function Engine-Up($p) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect('127.0.0.1', $p); return $c.Connected }
    catch { return $false }
    finally { $c.Close() }
}

function Read-Lines($path) {
    if (-not $path -or -not (Test-Path $path)) { return @() }
    try {
        $fs = New-Object System.IO.FileStream($path, 'Open', 'Read', 'ReadWrite')
        $sr = New-Object System.IO.StreamReader($fs)
        $text = $sr.ReadToEnd()
        $sr.Close(); $fs.Close()
        return @($text.Replace("`r", '').Split("`n") | Where-Object { $_ -ne '' })
    } catch { return @() }
}

function Json-Array($lines) {
    if ($lines.Count -eq 0) { return '[]' }
    if ($lines.Count -eq 1) { return '[' + (ConvertTo-Json -Compress -InputObject $lines[0]) + ']' }
    return ConvertTo-Json -Compress -InputObject $lines
}

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
try { $listener.Start() } catch { exit 0 }   # port taken - give up quietly

$deadline = (Get-Date).AddMinutes(30)
try {
    while ((Get-Date) -lt $deadline) {
        if (Engine-Up $EnginePort) { break }   # console is up; the page redirects itself
        if (-not $listener.Pending()) { Start-Sleep -Milliseconds 250; continue }
        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $stream.ReadTimeout = 200
            $buf = New-Object byte[] 2048
            try { [void]$stream.Read($buf, 0, $buf.Length) } catch {}   # drain the request, ignore it

            $body = '__asterismLog(' + (Json-Array (Read-Lines $LogPath)) + ')'
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
            $head = "HTTP/1.0 200 OK`r`n" +
                    "Content-Type: application/javascript`r`n" +
                    "Content-Length: $($bytes.Length)`r`n" +
                    "Cache-Control: no-store`r`n" +
                    "Connection: close`r`n`r`n"
            $hb = [System.Text.Encoding]::ASCII.GetBytes($head)
            $stream.Write($hb, 0, $hb.Length)
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush()
        } catch {}
        finally { $client.Close() }
    }
} finally {
    try { $listener.Stop() } catch {}
}
