$ErrorActionPreference = 'Stop'
$base = 'http://localhost:8000'
$results = @()

function Invoke-Step($name, [scriptblock]$action) {
  try {
    $data = & $action
    $script:results += [ordered]@{ step = $name; ok = $true; data = $data }
    return $data
  } catch {
    $script:results += [ordered]@{ step = $name; ok = $false; error = $_.Exception.Message }
    throw
  }
}

try {
  $admin = Invoke-Step 'admin login' {
    $body = @{ email = 'admin'; password = 'admin'; role = 'admin' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -ContentType 'application/json' -Body $body -TimeoutSec 120
  }
  $adminToken = $admin.access_token

  $teacherUser = "teacher-$([guid]::NewGuid().ToString('N').Substring(0,6))"
  $teacherPass = 'teachpass123'
  $teacher = Invoke-Step 'create teacher' {
    $body = @{ username = $teacherUser; password = $teacherPass; full_name = 'Test Teacher' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/admin/teachers" -ContentType 'application/json' -Headers @{ Authorization = "Bearer $adminToken" } -Body $body -TimeoutSec 120
  }

  $teacherLogin = Invoke-Step 'teacher login' {
    $body = @{ email = $teacherUser; password = $teacherPass; role = 'teacher' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -ContentType 'application/json' -Body $body -TimeoutSec 120
  }
  $teacherToken = $teacherLogin.access_token

  $studentId = "s-$([guid]::NewGuid().ToString('N').Substring(0,8))"
  $studentUser = "student-$([guid]::NewGuid().ToString('N').Substring(0,6))"
  $studentPass = 'studpass123'
  $student = Invoke-Step 'create student' {
    $body = @{ student_id = $studentId; username = $studentUser; password = $studentPass; full_name = 'Test Student'; age = 11; reading_age = 9; learning_style = 'general'; interests = @('chess'); neuro_profile = @('general') } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/teacher/students" -ContentType 'application/json' -Headers @{ Authorization = "Bearer $teacherToken" } -Body $body -TimeoutSec 120
  }

  $studentLogin = Invoke-Step 'student login' {
    $body = @{ email = $studentUser; password = $studentPass; role = 'student' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" -ContentType 'application/json' -Body $body -TimeoutSec 120
  }
  $studentToken = $studentLogin.access_token

  $conversationId = [guid]::NewGuid().ToString()
  $question = Invoke-Step 'tutor question' {
    $questionText = [System.Text.RegularExpressions.Regex]::Unescape("\u0d15\u0d48\u0d15\u0d34\u0d41\u0d15\u0d32\u0d4d \u0d0e\u0d28\u0d4d\u0d24\u0d15\u0d4b\u0d23\u0d4d\u0d1f\u0d4d \u0d2a\u0d4d\u0d30\u0d27\u0d3e\u0d28\u0d2e\u0d3e\u0d23\u0d4d?")
    $body = @{ student_id = $studentId; conversation_id = $conversationId; question = $questionText; context = @{ } } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/tutor/question" -ContentType 'application/json' -Headers @{ Authorization = "Bearer $studentToken" } -Body $body -TimeoutSec 180
  }

  $answer = Invoke-Step 'tutor answer' {
    $body = @{ student_id = $studentId; conversation_id = $conversationId; turn_id = $question.turn_id; student_answer = 'Handwashing removes germs and prevents disease.'; check_answer_hint = $question.check_answer_hint } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/api/tutor/answer" -ContentType 'application/json' -Headers @{ Authorization = "Bearer $studentToken" } -Body $body -TimeoutSec 180
  }
}
catch {
  # Stop early if any step failed
}

$outPath = 'output/api_flow_run.json'
$results | ConvertTo-Json -Depth 12 | Out-File -Encoding UTF8 $outPath
Write-Host "Saved results to $outPath"
