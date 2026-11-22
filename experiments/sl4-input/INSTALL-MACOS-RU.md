# Установка экспериментальных клавиатуры и тачпада из macOS (без USB)

Только Microsoft Surface Laptop 4 Intel (Tiger Lake-U, UART `8086:A0A8`) с уже установленной macOS Tahoe и работающим OpenCore 1.0.8. Код **экспериментальный**: пока подтверждены лишь синтетические тесты установщика. Реальная работа встроенного ввода **не подтверждена**.

Установщик работает **из macOS**, не требует перехода в Windows и ничего не меняет в Microsoft EFI, таблице разделов, NVRAM и работающем Metal 2. Требует штатный пакет Xcode Command Line Tools, иначе на Mac отсутствуют `python3`, `git` и `clang`. Необходимы интернет и внешняя клавиатура/мышь для отката при проблемах.

**Все команды — однострочные. Выполняй последовательно; при ошибке остановись.**

1. Если Command Line Tools не установлены: `xcode-select --install`. Заверши установку в открывшемся окне.
2. Убедись, что инструменты доступны: `xcode-select -p && python3 --version && git --version`.
3. Загрузи билд-скрипт и безопасный macOS-установщик:

   `curl -fL --retry 3 'https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-sam-keyboard-trackpad/experiments/sl4-input/build-bigsurface-sl4.py' -o "$HOME/Downloads/build-bigsurface-sl4.py" && curl -fL --retry 3 'https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-sam-keyboard-trackpad/experiments/sl4-input/stage-surface-input-macos.py' -o "$HOME/Downloads/stage-surface-input-macos.py"`

4. Компилируй пять kext из закреплённых исходников BigSurface (на macOS с CLT):

   `python3 "$HOME/Downloads/build-bigsurface-sl4.py"`

5. Упакуй результат (только если успешно скомпилировано пять kext):

   `cd "$HOME/Downloads/bigsurface-sl4" && /usr/bin/zip -qyr "$HOME/Downloads/SL4-BigSurface-EXPERIMENTAL.zip" out`

6. Загрузить официальный `ocvalidate` той же версии, что и текущий OpenCore (1.0.8):

   `curl -fL --retry 3 'https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip' -o "$HOME/Downloads/OpenCore-1.0.8-RELEASE.zip" && mkdir -p "$HOME/Downloads/OC108-validate" && ditto -xk "$HOME/Downloads/OpenCore-1.0.8-RELEASE.zip" "$HOME/Downloads/OC108-validate" && chmod +x "$HOME/Downloads/OC108-validate/Utilities/ocvalidate/ocvalidate"`

7. Прочитай текущую EFI и проверь архив (без записи):

   `sudo diskutil mount readOnly disk0s1; python3 "$HOME/Downloads/stage-surface-input-macos.py" --mode inspect --efi /Volumes/SYSTEM/EFI --artifact "$HOME/Downloads/SL4-BigSurface-EXPERIMENTAL.zip"`

8. Только после успешной проверки и при наличии независимого доступа к Windows Boot Manager переключи ESP из read-only в read-write:

   `sudo diskutil unmount disk0s1 && sudo diskutil mount disk0s1`

9. Выполни установку с полным OC-бэкапом и Windows-доступным файлом отката:

   `sudo python3 "$HOME/Downloads/stage-surface-input-macos.py" --mode apply --efi /Volumes/SYSTEM/EFI --artifact "$HOME/Downloads/SL4-BigSurface-EXPERIMENTAL.zip" --backup-dir "$HOME/Downloads/SL4-INPUT-BACKUPS" --ocvalidate "$HOME/Downloads/OC108-validate/Utilities/ocvalidate/ocvalidate" --ack STAGE-SL4-INPUT`

10. Только если сообщено `STAGED AND VALIDATED`:

   `sync && sudo diskutil unmount disk0s1`

11. Перезагрузи Tahoe и проверь физически клавиатуру, тачпад, Metal 2, Wi-Fi. Проверка загруженных драйверов: `kmutil showloaded 2>/dev/null | grep -Ei 'BigSurface|VoodooSerial|VoodooGPIO|VoodooInput'`.

## Откат

Установщик создаёт два экземпляра восстановления:
- полный `EFI/OC` в `~/Downloads/SL4-INPUT-BACKUPS/SL4-INPUT-*/OC` на macOS APFS;
- **точный оригинальный `config.plist`** в `S:\EFI\SL4-INPUT-ROLLBACK-*.plist` (тот же EFI-раздел, доступен из Windows). Восстановление исходного конфига вновь отключит новые пять kext и вернёт предыдущие драйверы даже без доступа к APFS.

Если Tahoe не загрузилась, в Windows через *самостоятельную* запись Windows Boot Manager смонтируй `S:` и верни последний `SL4-INPUT-ROLLBACK-*.plist` на место `S:\EFI\OC\config.plist`. Не стирай EFI или APFS.

Если Tahoe загружается и нужно восстановить полностью старый `EFI/OC`, macOS-установщик поддерживает `--mode restore --backup /Users/surface/Downloads/SL4-INPUT-BACKUPS/SL4-INPUT-<timestamp> --ack RESTORE-SL4-INPUT`; предварительно смонтируй `disk0s1` для записи.

Профиль использует штатный `\_SB.SSH` MSHW0084, UART `\_SB.PC00.UA00`, GPIO `\_SB.GPI0` IRQ `0x012A`. Отдельный SSDT-SAM от SL5 **не нужен**. Экспериментальный BigSurface отключает конфликтующие VoodooI2C и SMCBatteryManager только в конфигурации OpenCore; текущий графический драйвер не меняется.

Исходный проект: [PR #2](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/pull/2). Источники: [linux-surface ACPI SL4 Intel](https://github.com/linux-surface/acpidumps/blob/master/surface_laptop_4_intel/ssdt9.dsl), [BigSurface](https://github.com/Xiashangning/BigSurface).
