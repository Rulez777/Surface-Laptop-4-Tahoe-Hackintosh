/*
 * RESEARCH ONLY — Surface Laptop 4 Intel 13.5-inch experimental lid wake SSDT.
 *
 * Current firmware capture (2026-11-24): DSDT defines \_SB.LID0 (PNP0C0D)
 * and \_GPE._L4B, whose handler updates LIDS and notifies LID0. LID0 has no
 * _PRW in the DSDT or any of the eight firmware SSDTs. The active OpenCore
 * ACPI Add list has no other LID0 _PRW. Linux surface_gpe matches the SL4
 * Intel 13-inch SKU to GPE 0x4B and explicitly marks that GPE as a wake source.
 *
 * This candidate exposes GPE 0x4B to Darwin through LID0._PRW. It does not
 * modify the GPE registers, the _L4B handler, LPS0/LXEN, EC or SAM GPIO code.
 *
 * EXPERIMENTAL: AppleACPIPlatform must actually honor the _PRW entry. The
 * Surface's TGL graphics stack has known re-sleep-after-dark-wake risks.
 * Keep external keyboard attached, test one supervised lid-close/open cycle,
 * and immediately roll back if re-sleep hangs, repeated dark wakes occur,
 * the display stays dark, or GPU recovery increments. Automatic sleep stays
 * disabled. Do not treat this as a general sleep fix or publish as universal.
 *
 * Darwin only: the non-Darwin return does not advertise a usable sleep state.
 */
DefinitionBlock ("", "SSDT", 2, "SL4", "LIDWAK", 0x00000002)
{
    External (\_SB_.LID0, DeviceObj)

    Scope (\_SB.LID0)
    {
        Method (_PRW, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (Package (0x02) { 0x4B, 0x03 })
            }

            Return (Package (0x02) { 0x4B, Zero })
        }
    }
}
