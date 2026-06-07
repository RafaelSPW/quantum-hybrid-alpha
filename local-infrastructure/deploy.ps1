# deploy.ps1 — Actualiza el processor en Cloud Run (build + push + deploy + limpieza)
# Uso: desde local-infrastructure/, correr: .\deploy.ps1

$PROJECT   = "agenteahc"
$REGION    = "us-central1"
$REPO      = "quantum-compliance"
$SERVICE   = "quantum-processor"
$IMAGE_BASE = "us-central1-docker.pkg.dev/$PROJECT/$REPO/processor"

$envPath = "$PSScriptRoot\.env"
$keyPath = "$PSScriptRoot\serviceAccountKey.json"

# --- Leer credenciales ---
$envVars = @{}
Get-Content $envPath | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]+)=(.+)$') { $envVars[$matches[1].Trim()] = $matches[2].Trim() }
}
$firebaseB64 = [System.Convert]::ToBase64String(
  [System.Text.Encoding]::UTF8.GetBytes((Get-Content $keyPath -Raw))
)

# --- Paso 1: Build + Push via Cloud Build ---
Write-Host "`n[1/3] Construyendo y subiendo imagen a Artifact Registry..." -ForegroundColor Cyan
$buildConfig = "$PSScriptRoot\cloudbuild-buildonly.yaml"
$buildResult = gcloud builds submit --config $buildConfig --project=$PROJECT . 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR en el build:" -ForegroundColor Red
  $buildResult | Select-String -Pattern "ERROR|error" | Select-Object -Last 10
  exit 1
}
Write-Host "Build OK." -ForegroundColor Green

# --- Paso 2: Deploy a Cloud Run ---
Write-Host "`n[2/3] Desplegando en Cloud Run..." -ForegroundColor Cyan
$deployResult = gcloud run deploy $SERVICE `
  --image="$IMAGE_BASE`:latest" `
  --region=$REGION --project=$PROJECT --platform=managed `
  --no-allow-unauthenticated --min-instances=1 --max-instances=1 `
  --memory=1Gi --cpu=1 --timeout=540 `
  "--set-env-vars=FIREBASE_STORAGE_BUCKET=agenteahc.firebasestorage.app,GEMINI_API_KEY=$($envVars['GEMINI_API_KEY']),PAYPAL_CLIENT_ID=$($envVars['PAYPAL_CLIENT_ID']),PAYPAL_CLIENT_SECRET=$($envVars['PAYPAL_CLIENT_SECRET']),FIREBASE_CREDENTIALS_B64=$firebaseB64" `
  2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR en el deploy:" -ForegroundColor Red
  $deployResult | Select-String -Pattern "ERROR|error" | Select-Object -Last 5
  exit 1
}
Write-Host "Deploy OK." -ForegroundColor Green

# --- Paso 3: Borrar imágenes viejas (dejar solo la última) ---
Write-Host "`n[3/3] Limpiando imágenes viejas..." -ForegroundColor Cyan
$allImages = gcloud artifacts docker images list "$IMAGE_BASE" `
  --project=$PROJECT --format="value(version)" --sort-by="~updateTime" 2>&1 |
  Where-Object { $_ -match "^sha256:" }

if ($allImages.Count -gt 1) {
  $toDelete = $allImages | Select-Object -Skip 1
  foreach ($digest in $toDelete) {
    Write-Host "  Eliminando $digest..."
    gcloud artifacts docker images delete "$IMAGE_BASE@$digest" `
      --project=$PROJECT --quiet --delete-tags 2>&1 | Out-Null
  }
  Write-Host "Limpieza OK — se eliminaron $($toDelete.Count) imagen(es) vieja(s)." -ForegroundColor Green
} else {
  Write-Host "Solo hay una imagen, nada que limpiar." -ForegroundColor Green
}

Write-Host "`nDeploy completado." -ForegroundColor Cyan
