$env:Path = "$PSScriptRoot\.tools\gogcli;$env:APPDATA\npm;$env:Path"
$env:GOG_ACCOUNT = "abdurakhmonkuchkorov@gmail.com"

& "$env:APPDATA\npm\openclaw.cmd" gateway run
