# Исправление npm audit и размера frontend chunks

## Состояние

- 2026-10-21: пользователь одобрил план сообщением «да» (Gate 1).
- 2026-10-21: пользователь принял общий результат сообщением «да» (Gate 2). Работа завершена.
- Точечное исправление frontend build tooling; OpenSpec и ADR не требуются.

## Проверенные причины

- Актуальный `npm audit --json` сообщает одну high vulnerability в прямой dev-зависимости `vite@8.3.0`: несколько advisories затрагивают 8.3.0–8.3.2; рекомендуемое исправление — 8.3.5, без major upgrade.
- В `frontend/vite.config.ts` отсутствует настройка разделения зависимостей на chunks. Текущий dist: основной JS 617.66 kB, CardDetailsPage 366.95 kB по представленному build log; имена файлов совпадают с локальным dist.
- Маршрут CardDetailsPage уже использует lazy import; сохранить эту границу загрузки графика.
- Repowise index соответствует HEAD (1d31946d57ef); запрошен риск для config/manifest/lock. Статический граф не учитывает все потребители конфигурации сборки.
- Context7: актуальная документация Vite подтверждает `build.rolldownOptions.output.codeSplitting.groups`.
- Funding — информационное сообщение npm.

## План для одобрения

1. Обновить только Vite до точной 8.3.5 с согласованным package-lock; не применять массовый `npm audit fix --force`.
2. В vite.config.ts разделить runtime-зависимости на небольшое число осмысленных chunks (React/runtime, router, Radix/UI при необходимости), используя Rolldown codeSplitting.groups. Сохранить lazy загрузку страницы с графиком. Лимит предупреждения 500 kB не повышать.
3. Проверить npm ci и npm audit, frontend lint, существующие unit-тесты, mock browser E2E и полную desktop:build. Сравнить размеры JS и общий dist до/после, проверить отсутствие chunk warning и работоспособность lazy перехода на карточку.
4. Представить diff, проверки и оставшиеся ограничения для явной приёмки (Gate 2).

## Границы и критерии

- Ожидаемые прикладные изменения: frontend/package.json, frontend/package-lock.json, frontend/vite.config.ts.
- Критерии: npm audit без уязвимостей; desktop build без JS chunks >500 kB; проходят существующие frontend проверки; сохранён отложенный маршрут карточки.
- Возможный эффект: изменятся имена/количество JS assets и порядок их загрузки; E2E и сборка проверяют регрессии. Mock E2E не проверяет live Tauri WebView.
- API, Rust, Python, worker, CLI, numeric JSON, БД и миграции не затрагиваются.

## Реализация и проверки

- Vite зафиксирован на 8.3.5; lock обновляет его build-зависимости Rolldown/bindings, OXC types, PostCSS и nanoid. Пакеты не добавлены и не удалены.
- В vite.config.ts добавлена одна группа react-runtime для react/react-dom/scheduler; другие библиотеки и прикладной код не менялись. Лимит 500 kB сохранён.
- `npm ci` и отдельный `npm audit --json`: успешно, 0 vulnerabilities.
- `npm test`: 9 файлов, 20 тестов прошли.
- `rtk bypass npm run lint`: успешно. Первый запуск через RTK wrapper вернул ошибку разбора ESLint JSON вместо результата TypeScript; прямой повтор выполнен из-за непригодного вывода wrapper.
- `npm run desktop:build`: успешно, release binary собран; предупреждения о chunks >500 kB нет.
- `git diff --check`: успешно.
- Отдельная production mock-сборка в `/tmp/price-watch-chunks-qa` и Playwright smoke на http://127.0.0.1:5176: заголовок Price Watch, каталог -> /cards/1 -> видимый график; CardDetailsPage отсутствует среди начальных JS requests и запрашивается при переходе; pageerror/console.error отсутствуют. Скриншот `/tmp/price-watch-chunks-production.png`. Preview остановлен после проверки. Browser plugin не доступен, использован установленный Playwright. Live Tauri WebView не запускался.
- Полный существующий mock E2E: 34/35 прошли за 6 минут (31 сценарий app.spec.ts и 4 layout.spec.ts). Падает сценарий «фильтры не сдвигаются…» на ожидании AirPods в сетке (app.spec.ts:381). Оно воспроизведено тем же assertion на исходном HEAD в `/tmp/price-watch-audit-baseline` с исходным lock и Vite 8.3.0 (`npm ci`, отдельный порт 5177, `playwright test --grep 'фильтры не сдвигаются'`): существующий дефект, вне текущего исправления build tooling. В dev E2E также видны React Router HydrateFallback warnings; production smoke ошибок не выявил.

### Размеры desktop dist

| Файл | До, kB | После, kB |
|---|---:|---:|
| index JS | 617.66 | 397.99 |
| React runtime | — | 218.75 |
| Rolldown runtime | — | 0.72 |
| CardDetailsPage | 366.95 | 366.90 |

Полный dist: 1 072 939 -> 1 072 868 байт (−71 байт). Основной эффект — разделение файлов, общий объём практически тот же.

## Следующее действие

### Уточнение причины E2E по запросу пользователя

- Пользователь потребовал выяснить и устранить причину падения, исправив приложение либо неверный тест. Диагностика выявила ошибку приложения, логика ожидания всех карточек верна.
- После клика «Сбросить» URL уже `/cards`, но UI/обработчики ещё содержат старые search params из-за отложенного обновления React Router. Немедленный клик «Сетка» вызывает setParam со старым status и восстанавливает `/cards?status=deals_disabled&view=grid`; остаётся только LEGO. Поэтому AirPods не находится.
- Проверено отдельным Playwright-скриптом: без промежуточного ожидания сбой воспроизводится; с ожиданием «Все состояния» после сброса URL становится `/cards?view=grid`, видны все пять карточек. Это диагностическое сравнение, тест пока не изменён.
- Пересмотренный точечный план: синхронно применять сброс search params через поддерживаемый React Router `flushSync`, сохранив replace и текущий вид; усилить E2E проверками отсутствия status в конечном URL, состояния фильтра и полного набора карточек, сохранив быстрый переход после reset без искусственного ожидания. Проверить исходный сценарий повторными запусками, сброс в list/grid, lint/unit, полный E2E и desktop build.
- Новый прикладной файл: frontend/src/features/cards/CardsPage.tsx; тест: frontend/e2e/app.spec.ts. API/БД не затрагиваются. Пользователь одобрил конкретный пересмотренный план сообщением «давай» (Gate 1); Gate 2 для общего результата ещё не пройден.
- Сброс search params использует `{ replace: true, flushSync: true }`, сохраняя текущий вид. Изменение синхронного обновления ограничено действием reset.
- В E2E быстрые клики reset -> grid остаются соседними, без промежуточных ожиданий. После них проверяются чистый URL, все состояния, отсутствие reset и пять карточек. Дополнительно проверяется reset непосредственно в сетке с сохранением view=grid и всех пяти карточек.
- После правки lint и 20 unit-тестов прошли. Регрессионный сценарий с `--repeat-each=3`: 3/3 прошли за 49.8s. Повторный `npm audit --json`: 0 vulnerabilities. Повторный desktop build прошёл без chunk warning, основной JS 398.00 kB, полный dist 1 072 881 байт. Полный E2E: **35/35 прошли за 6 минут**. В dev E2E остаются предупреждения HydrateFallback; live Tauri WebView не проверялся.
- Итоговый diff ограничен package.json/package-lock, vite.config.ts, resetFilters в CardsPage.tsx и проверками существующего сценария app.spec.ts. `git diff --check` прошёл. Данные и контракты API/worker/CLI не менялись.
- 2026-10-21: пользователь принял реализацию и результаты проверок сообщением «да» (Gate 2). Работа завершена; OpenSpec не создавался, синхронизация и архивирование не требуются. По отдельному запросу пользователя изменения фиксируются коммитом задачи; push/merge не выполнялись.
