# Reports the working directory to qtxterm after every prompt, as OSC 7.
#
# Dot-sourced by qtxterm when it launches PowerShell, *after* the user's
# profile has run, so $function:prompt here is whatever the profile left -
# the original is called for its output and this only prefixes the escape
# sequence. PowerShell needs to be asked because, unlike cmd and bash, it
# does not update the process's own working directory when you `cd`, so
# there is nothing for the app to read from the outside.

if (-not $global:__qtxtermPromptWrapped) {
    $global:__qtxtermPromptWrapped = $true
    $global:__qtxtermInnerPrompt = $function:prompt

    function global:prompt {
        try {
            # ProviderPath, not Path: inside a PSDrive or a registry
            # location Path reads "HKLM:\...", and only ProviderPath is a
            # directory anything else could start in. It is empty for a
            # location with no filesystem path at all, hence the guard.
            $qtxtermPath = (Get-Location).ProviderPath
            if ($qtxtermPath) {
                # .Replace, not -replace: the latter takes a regex, in which
                # a lone backslash is a syntax error rather than a backslash.
                $qtxtermUrl = [uri]::EscapeUriString($qtxtermPath.Replace('\', '/'))
                # Empty host (file:///...) - the path is on this machine, and
                # it keeps the sequence the same shape as the other shells'.
                # BEL-terminated, which every terminal accepts and which
                # avoids ending a PowerShell string on a backslash.
                [Console]::Write("$([char]27)]7;file:///$qtxtermUrl$([char]7)")
            }
        } catch {
            # A prompt that throws leaves the shell unusable; a missing cwd
            # report only costs a split pane its starting directory.
        }
        & $global:__qtxtermInnerPrompt
    }
}
