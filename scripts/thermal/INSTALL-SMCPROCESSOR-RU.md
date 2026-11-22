# Surface Laptop 4 Intel — датчик CPU для Tahoe

**Назначение:** подключение `SMCProcessor.kext 1.3.8` к существующему `VirtualSMC.kext 1.3.8`. Без USB, без замены графического драйвера, BigSurface, батареи или Windows EFI.

Требования: Surface Laptop 4 Intel i7-1185G7 / UART `8086:A0A8`, Windows 11 и macOS Tahoe на внутреннем SSD, OpenCore 1.0.8, Python 3, Git, независимый Windows Boot Manager.

## Windows PowerShell (Администратор)

Все команды — по одной строке. Остановка при любой ошибке.

**1. Исходники проекта.**

~~~powershell
if (Test-Path "$HOME\Downloads\SL4-Tahoe-Git\.git") { git -C "$HOME\Downloads\SL4-Tahoe-Git" fetch origin experimental/sl4-thermal-guard; if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed' }; git -C "$HOME\Downloads\SL4-Tahoe-Git" switch -C experimental/sl4-thermal-guard origin/experimental/sl4-thermal-guard } else { git clone --branch experimental/sl4-thermal-guard https://github.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh.git "$HOME\Downloads\SL4-Tahoe-Git" }; if ($LASTEXITCODE -ne 0) { throw 'Git setup failed' }
~~~

**2. Официальный VirtualSMC 1.3.8 (только SMCProcessor).**

~~~powershell
curl.exe -fL --retry 3 "https://github.com/acidanthera/VirtualSMC/releases/download/1.3.8/VirtualSMC-1.3.8-RELEASE.zip" -o "$HOME\Downloads\VirtualSMC-1.3.8-RELEASE.zip"; if ($LASTEXITCODE -ne 0) { throw 'VirtualSMC download failed' }
~~~

Установщик проверяет состав архива, `CFBundleIdentifier`, версию `1.3.8`, Mach-O и зависимости. **Имеющийся VirtualSMC не заменяется.**

**3. Валидатор OpenCore 1.0.8.** Уже имеется в `$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe`. При отсутствии:

~~~powershell
curl.exe -fL --retry 3 "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip" -o "$HOME\Downloads\OpenCore-1.0.8-RELEASE.zip"; if ($LASTEXITCODE -ne 0) { throw 'OpenCore download failed' }; Expand-Archive -LiteralPath "$HOME\Downloads\OpenCore-1.0.8-RELEASE.zip" -DestinationPath "$HOME\Downloads\OC108-validate" -Force
~~~

Альтернативный путь валидатора: `$HOME\Downloads\OC108-validate\Utilities\ocvalidate\ocvalidate.exe`. В примерах ниже используется ранее подготовленный валидатор `SL4-FULL-DRIVERS`.

**4. Только внутренний ESP.**

~~~powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
~~~

**5. Проверка без записи в EFI.**

~~~powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\thermal\install_smcprocessor_windows.py" --mode inspect --efi "S:\EFI" --archive "$HOME\Downloads\VirtualSMC-1.3.8-RELEASE.zip"
~~~

Ожидается `INSPECT PASS: internal EFI untouched`. Проверки: Windows Boot Manager, SL4 Intel, UART A0A8, Lilu, VirtualSMC 1.3.8, BigSurface и архив плагина.

**6. Установка с резервной копией.** Только после успешного inspect.

~~~powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\thermal\install_smcprocessor_windows.py" --mode apply --efi "S:\EFI" --archive "$HOME\Downloads\VirtualSMC-1.3.8-RELEASE.zip" --ocvalidate "$HOME\Downloads\SL4-FULL-DRIVERS\tools\ocvalidate.exe" --backup-dir "$HOME\Downloads\SL4-SMC-BACKUPS" --ack INSTALL-SMC-SENSOR
~~~

Ожидается `STAGED AND VALIDATED`. Полная копия `EFI/OC` сохраняется на Windows `C:`. Добавляется ровно один `Kernel/Add` после VirtualSMC. Никаких изменений `EFI/Microsoft`, других kext или NVRAM.

~~~powershell
mountvol S: /D
~~~

Перезагрузка macOS.

## macOS Tahoe — только чтение

**7. Проверка загрузки SMCProcessor.**

~~~bash
kmutil showloaded 2>/dev/null | grep -Ei 'SMCProcessor|VirtualSMC|BigSurface'
~~~

**8. Проверка температуры процессора.**

~~~bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-thermal-guard/scripts/thermal/sl4_thermal_guard.py" -o "$HOME/Downloads/sl4_thermal_guard.py" && python3 "$HOME/Downloads/sl4_thermal_guard.py" --probe
~~~

Температура должна поступать из CPU die `TC0D` в °C. При ошибке `0x84`, неподдерживаемом формате или нереалистичных показаниях — **STOP; никаких автоматических команд контроллеру охлаждения**.

**9. Минутный мониторинг без управления вентилятором.**

~~~bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --monitor --samples 12
~~~

## Ограничение охлаждения SL4 Intel

Linux для `MSHW0250` поддерживает `TMP PerformanceMode`, но не независимый интерфейс оборотов `FAN`. `PerformanceMode=4` не означает 100% скорости вентилятора; профиль также может увеличить тепловыделение.

Экспериментальная температурная политика `80/72/90 °C` **не устанавливается как служба и не включается при запуске macOS**. Команды в этом документе не меняют профили Surface. Встроенные защиты процессора остаются обязательными.

## Откат через Windows, без USB

~~~powershell
if (!(Test-Path 'S:\EFI\OC\config.plist')) { mountvol S: /S }
~~~

**Точный путь** резервной копии выводится после установки. Пример синтаксиса с заменой отметки времени:

~~~powershell
py -3 "$HOME\Downloads\SL4-Tahoe-Git\scripts\thermal\install_smcprocessor_windows.py" --mode restore --efi "S:\EFI" --backup "$HOME\Downloads\SL4-SMC-BACKUPS\SL4-SMC-YYYYMMDD-HHMMSS-ffffff" --ack RESTORE-SMC-SENSOR
~~~

Откат возвращает исходный `config.plist` и удаляет только `SMCProcessor.kext`. При стороннем изменении текущей конфигурации восстановление блокируется; сохранённая полная копия `EFI/OC` остаётся доступна на Windows-диске.

## Источники

[VirtualSMC / SMCProcessor](https://github.com/acidanthera/VirtualSMC) · [Linux Surface registry](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_aggregator_registry.c) · [Linux Surface performance profiles](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_platform_profile.c)

**Готовность:** синтетические проверки установки и отката пройдены. Реальная работа CPU-датчика после загрузки плагина требует проверки.
