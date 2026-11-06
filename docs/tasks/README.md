# Задачи price-watch

Планы, отчёты, исследования и результаты проверок существующих задач сохранены
здесь вместе с вложениями. Их содержание и принятые решения не переписывались
при подключении нового flow; изменены расположение и ссылки.

Новые задачи ведутся по [vibe-flow](../guide/WORKFLOW.md): один технический
`openspec/changes/<name>/spec.md`, после приёмки — краткий итог в
[архиве OpenSpec](../../openspec/changes/archive/). Существующие изменения OpenSpec
сохраняют свои схему и артефакты, без автоматического преобразования.

[Backlog](../BACKLOG.md) — отдельный список будущих работ. Руководства,
[архитектура](../architecture/overview.md), [ADR](../adr/README.md) и
[постоянные спецификации](../../openspec/specs/) остаются на своих местах.

## Общие планы и чеклисты

- [Первоначальный план реализации](initial-implementation/plan.md).
- [Согласованный интерфейс и чеклист боковой панели](adopt-catalog-sidebar/implementation-checklist.md).

## Материалы задач

- [Коннектор AliExpress](add-aliexpress-connector.md)
- [Коннектор Wildberries](add-wildberries-connector.md)
- [Permanent catalog sidebar](adopt-catalog-sidebar.md)
- [Согласование названий проекта и модулей](align-project-and-module-names.md)
- [Фоновый трекинг цен](background-price-tracking.md)
- [Массовый выбор карточек и поиск при создании группы](bulk-card-selection-and-group-search.md)
- [Единая геометрия карточек](card-layout-uniformity.md)
- [Фильтр выгодности каталога](catalog-deal-filter.md)
- [Выгода и максимальная выгода в каталоге](catalog-maximum-savings.md)
- [Очистка зависимостей и удаление live web-режима](cleanup-dependencies-and-desktop-only-mode.md)
- [Cleanup notifications and tests](cleanup-notifications-and-tests.md)
- [Вычисляемые поля группы](compute-group-card-metrics.md)
- [Sidebar layout demos](demo-sidebar-layouts.md)
- [Редактирование полей карточки](edit-card-fields.md)
- [Исправление npm audit и размера frontend chunks](fix-frontend-audit-and-build-chunks.md)
- [Метаданные недоступной карточки Ozon](fix-ozon-unavailable-metadata.md)
- [Исправление геометрии UI после shadcn](fix-shadcn-ui-layout.md)
- [Фото Wildberries и вариантов товара](fix-wildberries-image.md)
- [Визуальное оформление групп — исследование](group-visual-design.md)
- [Надёжность сбора и согласованность каталога](harden-collection-reliability.md)
- [Аудит UI и план исправлений](improve-desktop-ui-usability.md)
- [Производительность UI и рост данных](improve-ui-and-data-performance.md)
- [Переход на shadcn/ui](migrate-ui-to-shadcn.md)
- [Ozon: JSON-запросы из общей браузерной сессии](ozon-session-json-transport.md)
- [Кнопка сброса рядом с переключателем вида](position-catalog-reset.md)
- [Сохранение авторизации Ozon при перезапуске Chrome](preserve-ozon-login-across-browser-restarts.md)
- [Товарные карточки и варианты SKU](product-variants-plan.md)
- [Remove seven-day deal wait](remove-seven-day-deal-wait.md)
- [Restore catalog UI performance](restore-catalog-ui-performance.md)
- [Отделение правил приложения от PostgreSQL — ARCH-03](separate-business-rules-from-postgres.md)
- [Все варианты карточки Ozon](track-ozon-product-variants.md)
- [Единый MarketplaceCard и отдельная запись отслеживания](unify-marketplace-card-model.md)
- [Цены без копеек](whole-ruble-display.md)
