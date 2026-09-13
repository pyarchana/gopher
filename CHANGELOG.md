# Changelog

Notable changes, newest first. Versions follow [semver](https://semver.org),
and `0.x` means the tool interface may still change between minor releases.

## 0.1.0

First release. Gopher is one MCP server exposing ten tools, merged from three
separate servers that are now archived: GopherFetch, GopherCache and
GopherDigest.

### Fetch

- `fetch_github_repo` returns a markdown digest of a public repository: the
  directory tree plus the contents of the files most worth reading.
- Output is capped by a total character budget, `GOPHER_DIGEST_BUDGET`,
  defaulting to 40,000. Spent on the tree first, then files in priority order.
  Previously a fixed ten files, which is not a size limit: measured across six
  real repositories, the same settings produced anywhere from 4,594 to 228,310
  characters, and anything past the client's ceiling was rejected whole.
- Ranking accounts for where a file sits, not only what it is called. A root
  manifest outranks a vendored copy of the same filename; test, fixture and
  vendor directories are demoted; locale-tagged copies of a document are
  demoted; files in the repository's primary language are favoured.
- A capped file listing is reported rather than presented as a complete tree.
  GitHub truncates recursive tree responses on large repositories, and the
  digest now says so.
- Files over 1MB are fetched through the blobs endpoint. The contents endpoint
  answers `200` with an empty body for those, so they previously vanished
  without a word.

### Memory

- `search_context` finds facts by substring across key paths and values. Key
  matches rank above value matches, results are bounded, and the reply reports
  the true total.
- `read_context` takes an optional dot path and returns one section.
- `update_context` refuses a write that would discard stored data, naming the
  key at fault, rather than crashing or silently replacing a whole section.
- The store is written atomically. A write that dies partway previously left an
  empty file and every subsequent read raised.
- Diary entries are split on their timestamp header, so an entry whose body
  contains its own markdown headings stays intact.

### Digest

- `digest_transcript` takes only a transcript path. It previously took the
  destination as an argument, which let the model choose any file on disk to
  overwrite.
- Model output is validated before anything is written. Numbers and booleans
  are accepted; lists and nested objects are refused with the key named.
- A fact that would destroy an existing section is refused and reported without
  abandoning the rest of the batch. An overwrite is applied but recorded, with
  both values, in the return value and the digest log.

### Project

- CI on Python 3.11 through 3.14, with ruff lint and format checks.
- 112 tests, including regression tests for every fixed defect, each verified
  to fail against the previous implementation.
- A landing page at https://pyarchana.github.io/gopher/, checked against the
  code by the test suite so the two cannot drift apart.
