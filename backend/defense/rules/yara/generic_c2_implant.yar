rule Generic_C2_Implant_Indicators
{
    meta:
        description = "Detects generic C2 implant indicators such as heartbeat loops, task polling, and module loaders."
        author = "Lucy Defense Platform"
        reference = "https://attack.mitre.org/tactics/TA0011/"
        mitre_attack = "T1071, T1059, T1105"
        confidence = "medium"
    strings:
        $hb1 = "heartbeat" ascii wide nocase
        $hb2 = "beacon" ascii wide nocase
        $hb3 = "sleep_mask" ascii wide nocase
        $poll1 = "/tasks" ascii wide
        $poll2 = "/results" ascii wide
        $poll3 = "get_task" ascii wide
        $mod1 = "run_module" ascii wide
        $mod2 = "download_module" ascii wide
        $mod3 = "module_loader" ascii wide
        $crypt1 = "AES-256-GCM" ascii wide
        $crypt2 = "ECDH" ascii wide
        $crypt3 = "HKDF" ascii wide
    condition:
        uint16(0) == 0x5A4D and
        (
            (2 of ($hb*)) and (1 of ($poll*)) and (1 of ($mod*))
        ) or
        (
            (1 of ($hb*)) and (1 of ($poll*) and 1 of ($crypt*))
        )
}
