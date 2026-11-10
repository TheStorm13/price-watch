# Frontend UI

Use the project shadcn skill (`../.agents/skills/shadcn/SKILL.md`) for UI work.
Read `components.json` or run `npx shadcn@latest info --json` from this directory
before selecting components. This application uses React/Vite, Tailwind 4,
Radix primitives (`asChild`), Lucide, and the official `@shadcn` registry.

- Reuse installed primitives in `src/components/ui`. Keep domain components in
  `src/components/product` and business logic in feature components/hooks.
- Search components/examples with the project shadcn MCP; fetch current docs
  through Context7 and `npx shadcn@latest docs <component>` before using APIs.
- Add only needed components through `npx shadcn@latest add @shadcn/<component>`.
  Inspect every generated file, imports, dependencies, and CSS state selectors.
  The CLI may emit `cn` imports: use the local `@/lib/utils` implementation.
  Radix states use `data-state`, so selectors must match the installed runtime.
- Update existing primitives with CLI `--dry-run` / `--diff` first. Preserve
  local variants and compact sizes; never overwrite without explicit approval.
- Use semantic colors and shared variants. Theme variables live in
  `src/styles/tokens.css`; Tailwind mappings and layer order live in
  `src/styles/global.css`. Keep the system font stack; no remote font loading.
- Use Select for dropdown choices so the popup follows the shared theme; a
  NativeSelect retains a system-rendered popup and needs an explicit UX reason.
- Forms use FieldGroup/Field and linked labels. Dialog/Sheet/AlertDialog need
  titles and descriptions. Preserve keyboard navigation, validation, pending
  states, and focus restoration, including transitions between overlays.
- Verify with relevant lint, unit, and mock E2E checks. Desktop builds and
  manual/native UI verification are handled by the user; run them only on an
  explicit request. Mock E2E does not verify live API, worker, database, or
  Tauri WebView. Any requested desktop QA must use isolated data.
