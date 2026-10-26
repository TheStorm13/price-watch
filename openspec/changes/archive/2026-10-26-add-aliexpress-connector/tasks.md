# Tasks

План, ADR 0008 и реализация приняты 2026-10-26. Все 16 задач выполнены;
спецификации синхронизированы, change архивирован.

## 1. Идентичность AliExpress и сохранность данных

- [x] 1.1 Реализовать parser/validation `productId:skuId` и полных .ru-ссылок, применить к API/create/update, CLI, transfer/store; проверить missing/conflicting/repeated SKU, URL mismatch, ASCII-only и длинные ID без JS number.
- [x] 1.2 Подготовить data-only Alembic migration с переносом только однозначных ссылок и preflight конфликтов; на disposable TEST_DATABASE_URL проверить сохранение card IDs/FK/history/settings, пропуск карточек без SKU без изменения их полей и отказ без изменений при дубликате или активном сборе.
- [x] 1.3 Проверить API/store/transfer roundtrip двух SKU одного productId и отклонение дубликата той же пары; подготовить заметки нового формата ввода/импорта и миграционных ограничений в workflow evidence для обновления руководств после принятия.

## 2. Общий Chrome lifecycle

- [x] 2.1 Вынести session/profile_lifecycle в marketplace_connector/browser, перевести Ozon и Rust closer, удалить старые реализации/шимы; проверить existing profile/browser tests, оба CLI imports и cargo check.
- [x] 2.2 Добавить acquire/release общего сеанса и согласование ручных challenge; проверить один процесс для двух клиентов, ранний release, acquire failure, отмену и normal close с synthetic cookie в отдельном временном профиле.
- [x] 2.3 Проверить регрессию Ozon raw/numeric без DATABASE_URL, parser/mapper/Decimal, overlap пяти fetch и независимую отмену; записать результаты и изменения архитектуры lifecycle в workflow evidence.

## 3. AliExpress adapter

- [x] 3.1 Реализовать response/model/parser/mapper/connector по очищенному productData fixture; проверить SKU identity, coupon/activity/regular priority, null/missing/zero, malformed/currency, 77648.00 для probe и отсутствие дополнительных цен в нормализованном JSON/snapshot.
- [x] 3.2 Проверить per-SKU stock, missing/duplicate SKU, неизвестные состояния, optional gallery/rating/attributes/seller, displayName вариантов и canonical URLs; подтвердить общий MarketplaceCard/JSON schema и database-free ProductService lookup.
- [x] 3.3 Реализовать session fetch с Ali storefront page, bounded retries/cooldown/recovery и отдельными AbortController; synthetic/browser tests должны подтвердить no product goto, пять пересекающихся fetch, 429/CAPTCHA/HTML/timeout/schema errors и отмену без влияния на Ozon.
- [x] 3.4 Подключить manual challenge handler в видимом и hidden/headless режимах; проверить продолжение после подтверждения, отказ после неуспешной проверки, последовательность ожиданий двух площадок и отмену; записать продуктовый путь проверки в workflow evidence.

## 4. Подключение к приложению и UI

- [x] 4.1 Объединить создание коннекторов direct collect/worker через builder с одним Chrome session; удалить AliExpress из pending-фильтров, проверить queued API/desktop, schedule/retry и mixed-run без повторной записи истории или потери lease. Проверить, что старая карточка без SKU получает ошибку «Не указан SKU» без запроса/save_result/изменения карточки и истории, а корректные соседние цели завершаются успешно.
- [x] 4.2 Обновить AddCardDrawer существующими shadcn Field/Input: productId/skuId и заполнение из полной ссылки; проверить форму, ошибки, focus/pending, разные варианты и убрать сообщение о недоступном сборе для AliExpress в unit/demo E2E.
- [x] 4.3 Убрать Ozon-only заголовок challenge, проверить текст AliExpress и продолжение в UI; прогнать frontend lint/unit/build и подготовить изменения пользовательских инструкций в workflow evidence без публикации до принятия.

## 5. Интеграционная проверка и review

- [x] 5.1 Запустить полный Python suite с disposable TEST_DATABASE_URL, применимые frontend demo E2E и Rust tests/desktop build; зафиксировать команды, результаты, пропуски и отличия demo от live проверки.
- [x] 5.2 Выполнить изолированный native smoke mixed-run и повторный live Ali SKU/Ozon smoke через текущий профиль без записи в пользовательскую БД; проверить одну цену Ali, отсутствие product navigations и штатное освобождение профиля, не сохранять secrets.
- [x] 5.3 Проверить diff, текущие consumers и risk analysis после lifecycle refactor; представить пользователю изменённые файлы, evidence, миграционные ограничения и риски для второго review, не объявляя завершение до принятия.

## Workflow follow-up

- После явного принятия обновить только затронутые руководства архитектуры/ввода/сбора/CAPTCHA/миграции на основе evidence групп 1–4 и статус ADR 0008.
- Выполнить sync specs и archive, проверить итоговые спецификации и git diff --check.
- Проверить staged diff и создать task-only commit(s), исключив чужое изменение docs/BACKLOG.md; проверить хеши и сообщить их. Push/merge не выполнять.
