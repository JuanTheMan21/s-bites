import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config([
  { ignores: ['dist', 'src/api/schema.d.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
  },
  {
    // The architectural seam (see src/domain/job.ts's own comment block): everything outside
    // src/api/ and src/adapters/ talks to the generated OpenAPI client only through domain/
    // types. This is what makes that a compile-time-checked rule instead of a convention nobody
    // remembers -- the frontend's equivalent of scripts/hook_boundary.py.
    files: ['src/features/**', 'src/components/**', 'src/routes/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/api/*', '**/api', 'openapi-fetch'],
              message:
                'features/, components/, and routes/ may not import src/api/ or openapi-fetch directly -- go through src/domain/ (mapped view models) or src/adapters/ (the mappers themselves). This keeps generated-contract churn out of the UI layer.',
            },
          ],
        },
      ],
    },
  },
])
