# Updating to a new Pixera version

`src/PixeraPy/api_functions.py` and `docs/api-reference.md` are generated. Do not edit them by hand.

1. Get the API description of the new Pixera version: `pixera_api_comments_revXXX.txt`
   (ships with Pixera / the Pixera API documentation package).
2. Put it into `api/`.
3. Regenerate:

   ```
   python tools/generate_api.py api/pixera_api_comments_revXXX.txt
   ```

   Aliases that cannot be created because two classes share a name are listed on stderr.
4. Update `test_generated_file_is_up_to_date` in `tests/test_api_functions.py` to the new file name
   and `test_revision` to the new revision, then run `pytest`. `test_old_calls_build_identical_requests`
   shows every function whose signature changed since revision 381; check those against the Pixera
   changelog and list them in `CHANGELOG.md`.
5. Bump `__version__` in `src/PixeraPy/__init__.py` to `0.<revision>.0`.

Comparing two descriptions (also works against the old `pixera_api_rev381.json`):

```
python tools/api_diff.py api/pixera_api_comments_revNEW.txt api/pixera_api_comments_revOLD.txt
```

Note: Pixera uses even revision numbers for releases and odd ones for betas.

The plain-text format prints functions that return a struct (e.g. `ScreenPosValues`) as returning
`null`. The generator restores the struct type from `api/pixera_api_rev381.json` where it is known.
