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

        $writeResult = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/write" -Method Post -ContentType "application/json" -Body $writeBody
        if ($writeResult.accepted_count -lt 1) {
            throw "Write acceptance failed."
        }

        $searchBody = @{
            query = "Docker Day 10"
            user_id = "demo-user"
            memory_space = "personal"
            limit = 5
        } | ConvertTo-Json -Depth 6

        $searchResult = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/search" -Method Post -ContentType "application/json" -Body $searchBody
        if ($searchResult.raw_count -lt 1) {
            throw "Search acceptance failed."
        }

        $dailyBody = @{
            date = "2026-05-12"
            user_id = "demo-user"
            memory_space = "personal"
            timezone = "UTC"
        } | ConvertTo-Json -Depth 6

        $dailyRecall = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/daily-recall" -Method Post -ContentType "application/json" -Body $dailyBody
        if ($dailyRecall.daily_recall.entry_count -lt 1) {
            throw "Daily recall acceptance failed."
        }

        $exportBeforeDelete = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/export?user_id=demo-user&memory_space=personal&format=json" -Method Get
        if ($exportBeforeDelete.count -lt 1) {
            throw "Export acceptance failed."
        }

        $deleteBody = @{
            ids = @($writeResult.memory_ids[0])
            user_id = "demo-user"
            memory_space = "personal"
        } | ConvertTo-Json -Depth 6

        $deleteResult = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/delete" -Method Post -ContentType "application/json" -Body $deleteBody
        if ($deleteResult.deleted_count -lt 1) {
            throw "Delete acceptance failed."
        }

        $exportAfterDelete = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/export?user_id=demo-user&memory_space=personal&format=json" -Method Get

        [pscustomobject]@{
            health = $health
            write = $writeResult
            search = $searchResult
            daily_recall = $dailyRecall
            export_before_delete = $exportBeforeDelete
            delete = $deleteResult
            export_after_delete = $exportAfterDelete
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
