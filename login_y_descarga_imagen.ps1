param(
  [Parameter(Mandatory = $true)]
  [string]$Usuario,

  [Parameter(Mandatory = $true)]
  [string]$Clave,

  [Parameter(Mandatory = $true)]
  [string]$PackageUrl,

  [string]$OutputDir = "."
)

$ErrorActionPreference = "Stop"

function Resolve-AbsoluteUrl {
  param(
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$Candidate
  )

  $clean = $Candidate.Trim()
  if ([string]::IsNullOrWhiteSpace($clean)) {
    return $null
  }

  try {
    $base = [System.Uri]$BaseUrl
    $uri = [System.Uri]::new($base, $clean)
    return $uri.AbsoluteUri
  } catch {
    return $null
  }
}

function Get-ImageUrlFromHtml {
  param(
    [Parameter(Mandatory = $true)][string]$Html,
    [Parameter(Mandatory = $true)][string]$BaseUrl
  )

  $patterns = @(
    '(?is)<div[^>]+id=["'']collapseMatProImg["''][^>]*>.*?<img[^>]+src=["''](?<u>[^"'']+)["'']',
    '(?is)<img[^>]+src=["''](?<u>[^"'']*?/Uploads/Material_Promocional/Thumb/[^"'']+)["'']',
    '(?is)<a[^>]+href=["''](?<u>[^"'']*?create_image_collage_new\.php[^"'']*)["'']',
    '(?is)<meta[^>]+property=["'']og:image["''][^>]+content=["''](?<u>[^"'']+)["'']',
    '(?is)<meta[^>]+name=["'']twitter:image["''][^>]+content=["''](?<u>[^"'']+)["'']'
  )

  foreach ($p in $patterns) {
    $m = [regex]::Match($Html, $p)
    if ($m.Success) {
      $url = Resolve-AbsoluteUrl -BaseUrl $BaseUrl -Candidate $m.Groups['u'].Value
      if ($url) {
        return $url
      }
    }
  }

  return $null
}

function Get-PreferredImageUrl {
  param(
    [Parameter(Mandatory = $true)][string]$DetectedUrl
  )

  # Prioriza calidad alta cuando la ruta encontrada es la miniatura.
  if ($DetectedUrl -match '/Thumb/') {
    return ($DetectedUrl -replace '/Thumb/', '/A4/')
  }

  return $DetectedUrl
}

if (-not (Test-Path -LiteralPath $OutputDir)) {
  New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$base = "https://www.operadorapuntadeleste.com"

Write-Host "[1/5] Abriendo pagina de acceso para iniciar sesion..."
Invoke-WebRequest -Uri "$base/acceso/" -WebSession $session -UseBasicParsing | Out-Null

Write-Host "[2/5] Enviando credenciales a login.asp..."
$loginResp = Invoke-WebRequest `
  -Uri "$base/login.asp" `
  -Method Post `
  -WebSession $session `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{ Usuario = $Usuario; Clave = $Clave } `
  -UseBasicParsing

$loginBody = ($loginResp.Content | Out-String).Trim()
if ($loginBody -eq "error") {
  throw "Login fallido: usuario o contrasena incorrectos."
}

Write-Host "[3/5] Login OK. Respuesta de login.asp: $loginBody"

# Si el backend devuelve una URL de redireccion, la abrimos para completar la sesion.
if (-not [string]::IsNullOrWhiteSpace($loginBody)) {
  $target = Resolve-AbsoluteUrl -BaseUrl $base -Candidate $loginBody
  if ($target) {
    Invoke-WebRequest -Uri $target -WebSession $session -UseBasicParsing | Out-Null
  }
}

Write-Host "[4/5] Cargando pagina del paquete autenticado..."
$pageResp = Invoke-WebRequest -Uri $PackageUrl -WebSession $session -UseBasicParsing
$html = $pageResp.Content

$imageUrl = Get-ImageUrlFromHtml -Html $html -BaseUrl $PackageUrl
if (-not $imageUrl) {
  throw "No se pudo detectar la imagen en la pagina autenticada."
}

Write-Host "Imagen detectada: $imageUrl"

$preferredImageUrl = Get-PreferredImageUrl -DetectedUrl $imageUrl
if ($preferredImageUrl -ne $imageUrl) {
  Write-Host "Version alta calidad sugerida: $preferredImageUrl"
}

Write-Host "[5/5] Descargando imagen..."
$downloadUrl = $preferredImageUrl
$fileName = [System.IO.Path]::GetFileName(([System.Uri]$downloadUrl).AbsolutePath)
if ([string]::IsNullOrWhiteSpace($fileName)) {
  $fileName = "imagen-promocional.jpg"
}

$outPath = Join-Path $OutputDir $fileName
try {
  Invoke-WebRequest -Uri $downloadUrl -WebSession $session -OutFile $outPath -UseBasicParsing
} catch {
  if ($downloadUrl -ne $imageUrl) {
    Write-Host "Fallo A4, reintentando con URL original..."
    $downloadUrl = $imageUrl
    $fileName = [System.IO.Path]::GetFileName(([System.Uri]$downloadUrl).AbsolutePath)
    if ([string]::IsNullOrWhiteSpace($fileName)) {
      $fileName = "imagen-promocional.jpg"
    }
    $outPath = Join-Path $OutputDir $fileName
    Invoke-WebRequest -Uri $downloadUrl -WebSession $session -OutFile $outPath -UseBasicParsing
  } else {
    throw
  }
}

Write-Host "Descarga completada: $outPath"
