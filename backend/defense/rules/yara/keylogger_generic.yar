rule Generic_Keylogger_Indicators
{
    meta:
        description = "Detects generic keylogger code patterns and API imports."
        author = "Lucy Defense Platform"
        reference = "https://attack.mitre.org/techniques/T1056/001/"
        mitre_attack = "T1056.001"
        confidence = "medium"
    strings:
        $api1 = "SetWindowsHookEx" ascii wide
        $api2 = "GetAsyncKeyState" ascii wide
        $api3 = "GetKeyboardState" ascii wide
        $api4 = "WH_KEYBOARD_LL" ascii wide
        $api5 = "MapVirtualKey" ascii wide
        $s1 = "keylog" ascii wide nocase
        $s2 = "keystroke" ascii wide nocase
        $s3 = "keyboard hook" ascii wide nocase
        $s4 = "logkeys" ascii wide nocase
    condition:
        (
            uint16(0) == 0x5A4D and
            (
                (2 of ($api*)) or
                (1 of ($api*) and 2 of ($s*))
            )
        ) or
        (
            3 of ($s*)
        )
}
