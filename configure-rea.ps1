$ErrorActionPreference = 'Stop'
$config = 'C:\Users\gijst\.codex\config.toml'
$text = [IO.File]::ReadAllText($config)
if ($text.Contains('[mcp_servers.rea.env]')) { throw 'Existing REA environment requires merge review' }
$addition = @'

[mcp_servers.rea.env]
GHIDRA_INSTALL_DIR = 'C:\Files\Apps\VCE Player\.tools\ghidra_12.1.4_PUBLIC'
JAVA_HOME = 'C:\Files\Apps\VCE Player\.tools\jdk-21.0.12.1+1'
'@
$backup = $config + '.before-rea-prereqs-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak'
Copy-Item -LiteralPath $config -Destination $backup
[IO.File]::WriteAllText($config, $text.TrimEnd() + [Environment]::NewLine + $addition + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Write-Output "Backup: $backup"
$env:GHIDRA_INSTALL_DIR = 'C:\Files\Apps\VCE Player\.tools\ghidra_12.1.4_PUBLIC'
$env:JAVA_HOME = 'C:\Files\Apps\VCE Player\.tools\jdk-21.0.12.1+1'
& "$env:JAVA_HOME\bin\java.exe" -version
& 'C:\Program Files\nodejs\node.exe' 'C:\Users\gijst\AppData\Local\npm-cache\_npx\ad9a3fdbcad992c6\node_modules\rea-agents\scripts\rea.mjs' doctor --client codex --json
