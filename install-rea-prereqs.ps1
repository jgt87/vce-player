$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Join-Path $PSScriptRoot '.tools'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$packages = @(
    @{Name='ghidra.zip'; Url='https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip'; Hash='ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db'},
    @{Name='jdk21.zip'; Url='https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip'; Hash='f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e'}
)
foreach ($package in $packages) {
    $archive = Join-Path $root $package.Name
    if (!(Test-Path -LiteralPath $archive)) {
        Write-Output "Downloading $($package.Name)"
        Invoke-WebRequest -Uri $package.Url -OutFile $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $package.Hash) { throw "Checksum mismatch: $archive" }
    Write-Output "Verified $($package.Name); extracting"
    Expand-Archive -LiteralPath $archive -DestinationPath $root -Force
}
& 'C:\Users\gijst\AppData\Local\Programs\Python\Python312\python.exe' -m venv (Join-Path $root 'frida-venv')
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
& (Join-Path $root 'frida-venv\Scripts\python.exe') -m pip install frida-tools
if ($LASTEXITCODE -ne 0) { throw 'Frida installation failed' }
& (Join-Path $root 'frida-venv\Scripts\frida.exe') --version
Get-ChildItem -LiteralPath $root -Directory | Select-Object FullName
