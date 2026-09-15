# Script de PowerShell para probar las APIs de visualizaciones avanzadas

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 PROBANDO APIS DE VISUALIZACIONES AVANZADAS" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "📅 Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Green

$baseUrl = "http://127.0.0.1:5000"
$endpoints = @(
    "/estadisticas/",
    "/estadisticas/api/kpis",
    "/estadisticas/api/heatmap", 
    "/estadisticas/api/prediction",
    "/estadisticas/api/profesores-actividad",
    "/estadisticas/api/flujo-recursos",
    "/estadisticas/api/rendimiento",
    "/estadisticas/api/timeline",
    "/estadisticas/visualizaciones"
)

$results = @{}

foreach ($endpoint in $endpoints) {
    $url = "$baseUrl$endpoint"
    Write-Host "`n🔍 Probando: $url" -ForegroundColor White
    
    try {
        $response = Invoke-WebRequest -Uri $url -Method GET -ErrorAction Stop
        $status = $response.StatusCode
        Write-Host "   Status: $status" -ForegroundColor Green
        
        if ($status -eq 200) {
            $contentType = $response.Headers["Content-Type"]
            if ($contentType -like "*application/json*") {
                try {
                    $jsonData = $response.Content | ConvertFrom-Json
                    if ($jsonData.success) {
                        Write-Host "   Success: $($jsonData.success)" -ForegroundColor Green
                        if ($jsonData.data) {
                            if ($jsonData.data -is [System.Array]) {
                                Write-Host "   Records: $($jsonData.data.Count)" -ForegroundColor Cyan
                            }
                            elseif ($jsonData.data -is [PSObject]) {
                                $keys = ($jsonData.data | Get-Member -MemberType NoteProperty).Name
                                Write-Host "   Keys: $($keys -join ', ')" -ForegroundColor Cyan
                            }
                        }
                    }
                    Write-Host "   ✅ JSON válido" -ForegroundColor Green
                }
                catch {
                    Write-Host "   ❌ JSON inválido: $($_.Exception.Message)" -ForegroundColor Red
                }
            }
            else {
                Write-Host "   ✅ HTML response" -ForegroundColor Green
            }
            $results[$endpoint] = $true
        }
        else {
            Write-Host "   ❌ Status: $status" -ForegroundColor Red
            $results[$endpoint] = $false
        }
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 302) {
            $location = $_.Exception.Response.Headers["Location"]
            Write-Host "   ↗️  Redirect to: $location" -ForegroundColor Yellow
            $results[$endpoint] = $false  # Redirect means need authentication
        }
        else {
            Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
            $results[$endpoint] = $false
        }
    }
}

# Resumen
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "📊 RESUMEN DE RESULTADOS" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

$passed = ($results.Values | Where-Object { $_ -eq $true }).Count
$total = $results.Count

foreach ($endpoint in $results.Keys) {
    $success = $results[$endpoint]
    $status = if ($success) { "✅ PASS" } else { "❌ FAIL" }
    $color = if ($success) { "Green" } else { "Red" }
    Write-Host "$status $endpoint" -ForegroundColor $color
}

Write-Host "`n🎯 Resultado: $passed/$total endpoints funcionando" -ForegroundColor Cyan

if ($passed -eq $total) {
    Write-Host "🎉 ¡Todas las APIs están funcionando correctamente!" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Algunas APIs necesitan autenticación o tienen problemas" -ForegroundColor Yellow
}