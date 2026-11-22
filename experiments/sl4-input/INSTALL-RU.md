# Surface Laptop 4 Intel — экспериментальная клавиатура и тачпад

Пакет состоит из **установщика для Windows 11** и тестов. Установщик работает с OpenCore на **внутренней EFI**, не требует флешки и не использует Xcode на Surface. Исходные коды драйверов и их автоматическая сборка: https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/tree/experimental/sl4-sam-keyboard-trackpad

**Поддерживаемый профиль:** Microsoft Surface Laptop 4 Intel, UART PCI `8086:A0A8`, существующая рабочая Tahoe + Metal 2. Для AMD Surface, Laptop 3/5 или другого UART установщик остановится. Это не означает, что клавиатура и тачпад уже проверены на SL4: для этого нужна удачная сборка и реальное испытание.

## Что проверяет установщик

- Модель компьютера и установленный в Windows Intel UART A0A8.
- Существующую Windows Boot Manager и OpenCore на внутреннем ESP; параметры работающего Metal 2 / DVMT 60 MB.
- Пять архивных `.kext`: правильные идентификаторы, исполняемые файлы Mach-O x86_64, соответствие UART/GPIO, отсутствие посторонних файлов.
- Перед записью копирует **весь `EFI/OC`** в отдельный каталог на Windows C:, сравнивает оригинальный `config.plist` с резервной копией.
- Отключает конфликтующие `VoodooI2C*` / `VoodooInput` / `SMCBatteryManager`; включает пять драйверов SAM HID в порядке зависимостей.
- Проверяет новую конфигурацию через `ocvalidate.exe` **OpenCore 1.0.8** и сверяет кext-файлы; при ошибке автоматически возвращает исходный `EFI/OC`.
- Предоставляет отдельный режим восстановления без форматирования ESP и изменения Windows BCD, разделов и NVRAM.

## Инструкция (каждая команда — одна строка)

Сначала в GitHub Actions ветки `experimental/sl4-sam-keyboard-trackpad` должен **успешно** выполниться workflow `Experimental Surface Laptop 4 keyboard / trackpad drivers`, появиться артефакт `SL4-BigSurface-EXPERIMENTAL.zip`. Если артефакта нет либо сборка неуспешна, **не переходите к установке**.

На **Windows 11**, запустите PowerShell от администратора, сохраните скрипт `SL4-Input-installer.py` в `Downloads`, скачайте артефакт GitHub Actions также в `Downloads`.

Подключение существующей внутренней EFI (если S: свободен):

`mountvol S: /S`

Проверка оборудования, EFI и архива без записи:

`py -3 "$HOME\Downloads\SL4-Input-installer.py" --mode inspect --efi "S:\EFI" --artifact "$HOME\Downloads\SL4-BigSurface-EXPERIMENTAL.zip"`

**Экспериментальная установка** — только после проверки успешной сборки и наличия независимого доступа к клавиатуре и мыши:

`py -3 "$HOME\Downloads\SL4-Input-installer.py" --mode apply --efi "S:\EFI" --artifact "$HOME\Downloads\SL4-BigSurface-EXPERIMENTAL.zip" --backup-dir "$HOME\Downloads\SL4-INPUT-BACKUPS" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe" --ack STAGE-SL4-INPUT`

Отмонтируйте ESP:

`mountvol S: /D`

После перезагрузки Tahoe проверяйте работу встроенной клавиатуры и тачпада, а также работающие Metal 2, Wi-Fi и внешний монитор. Даже если `ocvalidate` проходит, драйверы могут не заработать на реальном устройстве.

### Откат из Windows

Если Tahoe не загрузилась или клавиатура не работает, выберите независимую загрузку `Windows Boot Manager`, затем смонтируйте ESP:

`mountvol S: /S`

Посмотрите имена резервных каталогов `SL4-INPUT-*` в `C:\Users\<user>\Downloads\SL4-INPUT-BACKUPS` и замените `BACKUP-FOLDER` на свой:

`py -3 "$HOME\Downloads\SL4-Input-installer.py" --mode restore --efi "S:\EFI" --backup "$HOME\Downloads\SL4-INPUT-BACKUPS\BACKUP-FOLDER" --ack RESTORE-SL4-INPUT`

Затем `mountvol S: /D` и перезагрузите Tahoe. Восстановление откажется переписать EFI, если после установки её `config.plist` изменился — это защита от потери последующих изменений.

## Проверка самого установщика

В архиве `test_stage_surface_input.py` — пять тестов синтетической EFI: проверка архива, установка+откат, блокировка нерабочего Metal, отклонение посторонних файлов и дублированного бинарника. **Это не аппаратные испытания**.

Исходник и лицензия BigSurface: https://github.com/Xiashangning/BigSurface ; исходный порт SL5: https://github.com/Lulurala3119/BigSurface-for-Surface-Laptop-5 ; оригинальная ACPI таблица SL4: https://github.com/linux-surface/acpidumps/blob/master/surface_laptop_4_intel/ssdt9.dsl .
