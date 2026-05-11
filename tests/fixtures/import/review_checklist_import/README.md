# Review Checklist Import Fixtures

This directory stores the migrated fixtures for `审查清单 > 导入清单`.

## Canonical fixtures used by automation

- `valid-word.docx`
- `valid-excel.xlsx`
- `english-word.docx`
- `english-excel.xlsx`
- `valid-old-word.doc`
- `valid-old-excel.xls`
- `invalid-type.txt`

`valid-word.docx` / `valid-excel.xlsx` are the standard Chinese import samples.
`english-word.docx` / `english-excel.xlsx` are the standard English import samples used to verify imported checklist rules are not translated into Chinese.
`english-word.docx` intentionally uses paragraph-based rule blocks instead of Word tables.

## Archived files from the 2026-04-08 round

The full historical file set is preserved under `round_20260408/`, including:

- 10MB boundary file
- oversize file
- empty Word / Excel files
- scan-only Word file
- special-character filename sample
- batch import samples

Those archived files are kept so the suite can be expanded later without going back to the old project.
