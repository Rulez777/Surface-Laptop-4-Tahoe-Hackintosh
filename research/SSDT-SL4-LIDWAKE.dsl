/*
 * RESEARCH ONLY — not compiled, installed or tested.
 * Surface Laptop 4 Intel 13.5", GPE 0x4B for the lid (Linux surface_gpe).
 * Historical Linux ACPI dump: LID0 lacks _PRW, _GPE._L4B notifies LID0.
 *
 * DO NOT use if current firmware or other injected SSDTs define LID0._PRW.
 * DO NOT use until the unrelated full S0ix entry hang is solved and physical
 * recovery/rollback is verified. May cause repeated dark wake / GPU hang.
 *
 * A prior S0ixStandby project offers a machine-specific _PRW technique;
 * this separate Source-only prototype references ACPI standard semantics.
 */
DefinitionBlock ("", "SSDT", 2, "SL4", "LIDWAK", 0x00000001)
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
