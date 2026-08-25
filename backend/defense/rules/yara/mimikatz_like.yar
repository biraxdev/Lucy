rule Mimikatz_Like_Tool_Indicators
{
    meta:
        description = "Detects strings commonly found in Mimikatz-like credential dumping tools."
        author = "Lucy Defense Platform"
        reference = "https://attack.mitre.org/techniques/T1003/"
        mitre_attack = "T1003"
        confidence = "high"
    strings:
        $s1 = "sekurlsa" ascii wide
        $s2 = "kerberos" ascii wide
        $s3 = "wdigest" ascii wide
        $s4 = "Lsadump" ascii wide
        $s5 = "DumpCreds" ascii wide
        $s6 = "token::" ascii wide
        $s7 = "privilege::" ascii wide
        $s8 = "process::" ascii wide
        $s9 = "lsass.exe" ascii wide
        $a1 = "mimikatz" ascii wide nocase
    condition:
        uint16(0) == 0x5A4D and
        (
            ($a1) or
            (4 of ($s*))
        )
}
