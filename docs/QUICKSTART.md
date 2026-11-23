# Quick Start — установить macOS Tahoe на Surface Laptop 4

Начальная точка: **обычная Windows 10/11**, macOS заранее не нужна. Проект подготовит персональный загрузчик, Apple Recovery, драйверы и установочную флешку. После установки Tahoe этот же комплект поможет настроить оборудование.

## 1. Запуск в Windows

1. [Скачайте **Quick Start для Windows**](https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/releases/download/sl4-tahoe-v0.4.2-beta/SL4-Tahoe-Windows-QuickStart-v0.4.2-beta.zip). Нажмите **«Извлечь всё»**.
2. Дважды нажмите **`QuickStart.cmd`** в распакованной папке.
3. Выберите **1 — Install Tahoe from Windows**. Помощник определит оборудование, подготовит **уникальные личные идентификаторы OpenCore**, скачает оригинальные **Apple Recovery**, OpenCore и пакеты драйверов. При необходимости предложит установить Python.
4. Подключите **отдельную USB-флешку от 16 ГБ**, лучше от 32 ГБ. Помощник покажет только USB-диски; укажите нужный номер. На шаге записи запросит права администратора и отдельно подтвердит очистку **только выбранного USB-диска**. **Все данные на этой флешке будут удалены**. Windows на внутреннем SSD не форматируется.
5. По завершении появятся **MACOS-OC** (загрузчик + Apple Recovery) и **SL4DATA** (драйверы и инструменты). Не копируйте персональную `EFI/OC/config.plist` в открытые репозитории.

Программа готовит Apple Recovery, а не распространяет копию macOS. Во время самой установки требуется интернет: **предпочтительно USB-Ethernet или док-станция с проводным подключением**. Wi-Fi Intel AX201 может ещё не работать в среде Recovery.

## 2. Загрузка Tahoe

1. В Windows откройте **«Управление дисками»** и заранее выделите **свободное нераспределённое пространство** под macOS, сохранив разделы Windows, Microsoft Reserved и системную EFI. Сохраните ключ восстановления BitLocker, если он включён.
2. Войдите в Surface UEFI (выключите ноутбук, удерживайте **Volume Up** и нажмите **Power**), отключите **Secure Boot** для неподписанного OpenCore. Сохраните ключ восстановления BitLocker. Выключите Surface, подключите флешку, удерживайте **Volume Down** и нажмите **Power**.
   **В меню OpenCore стрелками выберите `macOS Base System (External)` (иногда `Recovery`) и нажмите Enter. Именно этот пункт открывает установочное Apple Recovery. Не выбирайте Windows Boot Manager или уже установленную macOS для первого входа в Recovery.** Новая USB-сборка показывает Recovery сразу и даёт 15 секунд на выбор. Если используется старая флешка и пункта нет, нажмите **Space (пробел)** в меню OpenCore, чтобы показать скрытые служебные пункты. После входа в Recovery ничего не стирайте, если вы только проверяете загрузку.
3. В **Дисковой утилите macOS** выберите **Вид → Показать все устройства**, создайте APFS-контейнер или том **только в заранее освобождённом пространстве** и установите Tahoe туда. **Не стирайте весь SSD и разделы Windows**.
4. Завершите установку, продолжая загружаться через USB OpenCore, пока macOS не будет успешно запускаться с внутреннего SSD.

## 3. Оборудование в Tahoe

На флешке откройте раздел **SL4DATA**, запустите `QuickStart-Mac.command`. Если macOS блокирует запуск файла двойным щелчком, откройте Terminal и выполните одну строку:

```bash
zsh "/Volumes/SL4DATA/QuickStart-Mac.command"
```

Выберите **1**. Помощник **в одном проходе** установит официальную графику WhateverXe Graphics 0.4.4, настроит проверенный драйвер **RCS single-port + DMC/eDP** в EFI USB, установит APOMac и оригинальный звуковой профиль Dolby Clear Speech, добавит автозапуск APOMac и создаст резервную копию OpenCore. Отдельный патч RCS и импорт звука **не нужны**. Затем перезагрузите Tahoe, продолжая использовать флешку. При первом запуске APOMac подтвердите разрешение macOS **System Audio Recording** — только этот системный запрос нельзя автоматизировать.

Драйверы **клавиатуры, тачпада и мультитач** (VoodooGPIO, VoodooSerial, VoodooInput, BigSurface и BigSurfaceHIDDriver) уже добавляются в персональную EFI ещё при подготовке Windows. Для Wi-Fi, Bluetooth, звука и яркости используйте пакет драйверов с раздела SL4DATA и [инструкцию для устройств](DRIVERS.md). Остальные компоненты можно выбрать и устанавливать раздельно, если конфигурация не совпадает с основной.

## 4. Загрузка без флешки (Windows + macOS)

Убедившись, что Tahoe действительно запускается через USB, вернитесь в **Windows** и снова откройте `QuickStart.cmd`, выберите **5 — Finish installation / Internal OpenCore**.

Помощник проверит USB OpenCore, отдельно сохранит BCD и загрузчик Windows, установит `EFI/OC` во внутреннюю EFI и при согласии создаст **отдельный пункт OpenCore**. `EFI/Microsoft` и исходная запись загрузки Windows сохраняются. При следующем включении выберите macOS/OpenCore в меню прошивки.

Если внутренний ESP уже содержит OpenCore, программа **не перезапишет его молча**: сначала сохраните и проверьте существующую конфигурацию через режим резервного копирования.

## Уже установлен Tahoe

В Windows `QuickStart.cmd` выберите **2 — Tahoe already installed**. Будет загружен самостоятельный пакет драйверов и инструментов восстановления. В macOS выберите **2** в QuickStart-Mac.command — он проверит RCS и установит нужное, включая Clear Speech. Можно выполнить:

```bash
zsh "/Volumes/SL4DATA/QuickStart-Mac.command"
```

или применить [установщик готового комплекта WhateverXe/DMC/S0ix](QUICKSTART-S0IX.md), если базовая графика уже работает. Для аудио, яркости, клавиатуры и беспроводных модулей применяйте соответствующие компоненты из [DRIVERS.md](DRIVERS.md).

## Advanced: другие версии и эксперименты

Выберите **3 — Advanced / Experiments** в Windows Quick Start для настройки источника Apple Recovery и экспериментальных драйверов. Рабочий профиль Surface Laptop 4 13.5″ — Intel i7-1185G7 и Iris Xe 8086:9A49. Другие версии Tahoe, Surface и периферия могут требовать собственной EFI и подбора драйверов — программа сохраняет возможность ручной настройки, не выдавая одну EFI за универсальную для всех ПК.

## Куда сохраняются данные

- `%USERPROFILE%\Downloads\SL4-Tahoe\Prepared` — созданные установочные комплекты.
- `%USERPROFILE%\Downloads\SL4-Tahoe\Cache` — загруженные файлы с проверкой SHA-256.
- `PRIVATE/identity.json` внутри каждого комплекта — **персональные идентификаторы**; не отправляйте их другим.
- При подготовке USB Windows на внутреннем SSD **остаётся нетронутой**.

**Оригинальные материалы:** <https://github.com/acidanthera/OpenCorePkg> (OpenCore и Apple Recovery), <https://github.com/b00t0x/WhateverXe>, <https://github.com/Xiashangning/BigSurface>. Требуется соблюдать лицензионные условия используемых компонентов.

## All-in-one audio and RCS (v0.4.1, 2026-11-23)

For Intel Surface Laptop 4 i7-1185G7 / Iris Xe 9A49 on **Tahoe 26.7.1**, see [RCS Stability 0.1.0 beta](QUICKSTART-RCS.md). The addon fixes a tested render-queue / preemption hang, and is installed **after** the graphics package and working Tahoe/DMC. Windows QuickStart 0.3.3 downloads and stages it for the Mac-side optional installer. It is not a fix for AV1/VP9 decoding; its preflight and private OpenCore rollback are mandatory. Do not install this kext on an unknown donor or the Windows installer USB.

Подробные проверки, ограничения Dolby и откат: [интегрированная графика и аудио](AUDIO-ALL-IN-ONE.md).

## Sleep and screen wake, corrected in v0.4.2

Установщик **не меняет** настройки питания macOS (`pmset`), не отключает автоматический сон и не подменяет его таймеры. Используются проверенные eDP Keep/Softsleep, DMC, S0ixStandby и RCS, сохраняя возможность пробуждения экрана после закрытия/открытия крышки и кнопкой питания. После первого запуска проверьте сон/пробуждение на своём устройстве. v0.4.1 ошибочно менял таймеры и не должен использоваться для новой установки.
