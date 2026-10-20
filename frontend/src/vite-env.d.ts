/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_E2E_TEST_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
