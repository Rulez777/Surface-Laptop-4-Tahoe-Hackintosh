# Surface Laptop 4 Intel — датчик температуры CPU в macOS Tahoe

**Платформа:** Surface Laptop 4 Intel i7-1185G7; macOS Tahoe 26.7.1; OpenCore 1.0.8; VirtualSMC 1.3.8; BigSurface 1.2.0.

**Цель:** подключить `SMCProcessor.kext` версии `1.3.8` для чтения CPU die `TC0D`. Установщик работает **полностью в macOS**, с внутреннего SSD, без USB и без переключения в Windows. Существующие VirtualSMC, BigSurface, графика Metal 2, клавиатура, тачпад, Bluetooth и батарея не меняются.

**Состояние:** `SMCProcessor.kext 1.3.8` загружен; датчик `TC0D` **работает**, получены показания 50–88 °C. Повторная установка не требуется. Автоматическая запись TMP при нагреве **отключена**: повышение профиля до `4` при 80 °C не является управлением вентилятором и может увеличить нагрев. Текущий диагностический сценарий: монитор температуры и разовая проверка `PerformanceMode=3`.

Все команды ниже однострочные; выполнять в **Терминале macOS** последовательно.

## 1. Загрузка установщика в macOS

~~~bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-thermal-guard/scripts/thermal/install_smcprocessor_macos.py" -o "$HOME/Downloads/install_smcprocessor_macos.py" && python3 --version
~~~

## 2. Официальный SMCProcessor 1.3.8

Загружается архив от [Acidanthera VirtualSMC](https://github.com/acidanthera/VirtualSMC/releases/tag/1.3.8). Установщик извлекает **только SMCProcessor**, проверяет идентификатор, версию, зависимости и Mach-O. Другие kext из архива не устанавливаются.

~~~bash
curl -fL --retry 3 "https://github.com/acidanthera/VirtualSMC/releases/download/1.3.8/VirtualSMC-1.3.8-RELEASE.zip" -o "$HOME/Downloads/VirtualSMC-1.3.8-RELEASE.zip"
~~~

## 3. OpenCore 1.0.8 ocvalidate для macOS

~~~bash
curl -fL --retry 3 "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/OpenCore-1.0.8-RELEASE.zip" -o "$HOME/Downloads/OpenCore-1.0.8-RELEASE.zip" && mkdir -p "$HOME/Downloads/OC108-validate" && ditto -xk "$HOME/Downloads/OpenCore-1.0.8-RELEASE.zip" "$HOME/Downloads/OC108-validate" && chmod +x "$HOME/Downloads/OC108-validate/Utilities/ocvalidate/ocvalidate"
~~~

## 4. Инспекция внутреннего EFI без записи

Монтирование **в режиме только чтения**:

~~~bash
sudo diskutil mount readOnly disk0s1
~~~

Проверка модели `MSHW0250`, Surface Serial Hub `MSHW0084`, расположения внутренней ESP, Windows Boot Manager как идентификатора раздела, включённых Lilu / VirtualSMC / BigSurface, сохранённой графической конфигурации, архива:

~~~bash
python3 "$HOME/Downloads/install_smcprocessor_macos.py" --mode inspect --archive "$HOME/Downloads/VirtualSMC-1.3.8-RELEASE.zip"
~~~

**Обязательный результат:** `INSPECT PASS: read-only; no EFI files changed`. При любой ошибке — **STOP**, дальнейшие шаги не выполнять.

## 5. Установка в существующую EFI

Перед записью монтирование раздела для записи:

~~~bash
sudo diskutil unmount disk0s1 && sudo diskutil mount disk0s1
~~~

Резервная копия **всего `EFI/OC`** — `~/Downloads/SL4-SMC-BACKUPS` на macOS APFS. Вспомогательный исходный `config.plist` сохраняется на внутреннем EFI как `EFI/SL4-SMC-ROLLBACK-*.plist`. Установщик меняет только список `Kernel/Add` (один новый пункт после VirtualSMC) и добавляет `OC/Kexts/SMCProcessor.kext`.

~~~bash
sudo python3 "$HOME/Downloads/install_smcprocessor_macos.py" --mode apply --archive "$HOME/Downloads/VirtualSMC-1.3.8-RELEASE.zip" --ocvalidate "$HOME/Downloads/OC108-validate/Utilities/ocvalidate/ocvalidate" --backup-dir "$HOME/Downloads/SL4-SMC-BACKUPS" --ack INSTALL-SMC-SENSOR
~~~

**Обязательный результат:** `STAGED AND VALIDATED: SMCProcessor 1.3.8 enabled`, полный путь резервной копии и исходного rollback-конфига.

~~~bash
sync && sudo diskutil unmount disk0s1
~~~

Перезагрузка macOS.

## 6. Проверка датчика после загрузки

Проверка загруженных модулей:

~~~bash
kmutil showloaded 2>/dev/null | grep -Ei 'SMCProcessor|VirtualSMC|BigSurface'
~~~

Проверка **реальной температуры CPU**, без команд охлаждению:

~~~bash
curl -fL --retry 3 "https://raw.githubusercontent.com/Rulez777/Surface-Laptop-4-Tahoe-Hackintosh/experimental/sl4-thermal-guard/scripts/thermal/sl4_thermal_guard.py" -o "$HOME/Downloads/sl4_thermal_guard.py" && python3 "$HOME/Downloads/sl4_thermal_guard.py" --probe
~~~

Результат должен содержать `Validated SMC CPU DIE TC0D = ... C`. При `0x84`, неправильном формате или невозможных значениях: **STOP, автоматическое управление не включать**.

Одна минута наблюдения за датчиком, без записи в EC:

~~~bash
python3 "$HOME/Downloads/sl4_thermal_guard.py" --monitor --samples 12
~~~

## 7. Откат из macOS

Точный путь резервной копии печатается на этапе установки. Пример пути в команде (заменить `YYYYMMDD-HHMMSS-ffffff`):

~~~bash
sudo diskutil mount disk0s1
~~~

~~~bash
sudo python3 "$HOME/Downloads/install_smcprocessor_macos.py" --mode restore --backup "$HOME/Downloads/SL4-SMC-BACKUPS/SL4-SMC-YYYYMMDD-HHMMSS-ffffff" --ack RESTORE-SMC-SENSOR
~~~

~~~bash
sync && sudo diskutil unmount disk0s1
~~~

При откате исходный `config.plist` восстанавливается из проверенной копии, удаляется **только** добавленный `SMCProcessor.kext`. При несовпадении контрольных сумм текущей конфигурации автоматический откат останавливается, сохраняя все данные.

Восстановление при невозможности загрузить macOS выполняется через любую сохранённую независимую загрузочную среду; вспомогательный исходный конфиг хранится на внутреннем EFI. **Не форматировать ESP и не трогать Windows EFI.**

## Ограничения охлаждения

SMCProcessor обеспечивает датчик, **не управляет оборотами вентилятора**. Surface Laptop 4 Intel использует `TMP PerformanceMode`, а не интерфейс прямого задания FAN RPM. Переход к `PerformanceMode=4` **не гарантирует максимальные обороты при 80 °C** и может повысить тепловыделение. Служба автоматического управления профилем остаётся экспериментальной и не запускается автоматически.

[Исходник Linux Surface](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_platform_profile.c) · [Интерфейсы устройства](https://github.com/torvalds/linux/blob/master/drivers/platform/surface/surface_aggregator_registry.c)

**Статус:** установка через macOS и откат подготовлены; аппаратная проверка после перезагрузки обязательна. Драйверы работающих устройств сохраняются.
