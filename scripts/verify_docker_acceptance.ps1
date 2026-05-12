param(
    [string]$ImageName = "soulark-memory-core",
    [string]$ContainerName = "soulark-memory-core-verify",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

Push-Location (Join-Path $PSScriptRoot "..")
try {
    docker build -t $ImageName .

    try {
        docker rm -f $ContainerName | Out-Null
    }
    catch {
    }

    docker run --rm -d --name $ContainerName -p "${Port}:8765" $ImageName | Out-Null
    try {
        $health = $null
        for ($i = 0; $i -lt 20; $i++) {
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -Method Get
                break
            }
            catch {
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $health) {
            throw "Container did not become healthy in time."
        }

        $writeBody = @{
            items = @(
                @{
                    user_id = "demo-user"
                    memory_space = "personal"
                    source_id = "docker-verify-001"
                    content = "Docker Day 10 验收开始。"
                    source = "docker-verify"
                    event_type = "raw_message"
                    sender = "user"
                    occurred_at = "2026-05-12T19:00:00+00:00"
                }
            )
        } | ConvertTo-Json -Depth 6

        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/write" -Method Post -ContentType "application/json" -Body $writeBody

        $dailyBody = @{
            date = "2026-05-12"
            user_id = "demo-user"
            memory_space = "personal"
            timezone = "UTC"
        } | ConvertTo-Json -Depth 6

        $dailyRecall = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/daily-recall" -Method Post -ContentType "application/json" -Body $dailyBody
        $exportResult = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/export?user_id=demo-user&memory_space=personal&format=json" -Method Get

        [pscustomobject]@{
            health = $health
            daily_recall = $dailyRecall
            export = $exportResult
        } | ConvertTo-Json -Depth 8
    }
    finally {
        try {
            docker rm -f $ContainerName | Out-Null
        }
        catch {
        }
    }
}
finally {
    Pop-Location
}