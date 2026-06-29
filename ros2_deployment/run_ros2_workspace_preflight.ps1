param(
    [string]$PackageName = "ros2_qgip_stack",
    [string]$FollowerNs = "/robot_1",
    [string]$LogDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($LogDir)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LogDir = "ros2_preflight_logs_$stamp"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Require-Command {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found on PATH: $Name"
    }
    return $cmd.Source
}

function Invoke-Logged {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    $logPath = Join-Path $LogDir "$Name.log"
    Write-Host "Running $Name; log: $logPath"
    & $Command *>&1 | Tee-Object -FilePath $logPath
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

# Run from a ROS2 workspace root that contains src/ros2_qgip_stack.
# This script prepares build/test evidence only; it does not command hardware.
$colconPath = Require-Command "colcon"
$ros2Path = Require-Command "ros2"
$pythonPath = Require-Command "python"

"colcon=$colconPath" | Out-File -FilePath (Join-Path $LogDir "environment.txt") -Encoding utf8
"ros2=$ros2Path" | Out-File -FilePath (Join-Path $LogDir "environment.txt") -Encoding utf8 -Append
"python=$pythonPath" | Out-File -FilePath (Join-Path $LogDir "environment.txt") -Encoding utf8 -Append
python --version | Out-File -FilePath (Join-Path $LogDir "environment.txt") -Encoding utf8 -Append

Invoke-Logged "colcon_build" { colcon build --packages-select $PackageName --event-handlers console_direct+ }
Invoke-Logged "colcon_test" { colcon test --packages-select $PackageName --event-handlers console_direct+ }
Invoke-Logged "colcon_test_result" { colcon test-result --verbose }

$setupPs1 = Join-Path (Get-Location) "install\setup.ps1"
if (Test-Path -LiteralPath $setupPs1) {
    . $setupPs1
}

Invoke-Logged "ros2_pkg_prefix" { ros2 pkg prefix $PackageName }
Invoke-Logged "ros2_launch_show_args" { ros2 launch $PackageName multi_robot_preflight.launch.py --show-args }

$launchArgs = Get-Content -LiteralPath (Join-Path $LogDir "ros2_launch_show_args.log") -Raw
foreach ($required in @("follower_ns", "max_speed_mps", "nis_hard_threshold", "results_csv_path")) {
    if ($launchArgs -notmatch [regex]::Escape($required)) {
        throw "Launch --show-args output missing required argument: $required"
    }
}

Invoke-Logged "pure_core_pytest" { python -m pytest "src\$PackageName\test" -q }

@"
ROS2 workspace preflight completed for $PackageName.
Follower namespace planned for later shadow inspection: $FollowerNs
No actuator bridge was enabled by this script.
Before Stage C/D evidence claims, record rosbag topics for $FollowerNs,
archive ros2 bag info/topic hz outputs, and fill hil_replay_manifest_template.yaml.
"@ | Out-File -FilePath (Join-Path $LogDir "README_preflight_result.txt") -Encoding utf8

Write-Host "ROS2 workspace preflight completed. Logs written to $LogDir"
