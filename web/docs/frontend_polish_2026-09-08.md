# Frontend review, 2026-09-08

Reviewed every primary route (projects, task shelf, task detail, Sky,
Groups, Engine, Timeline, Workspace, new task), Settings, and Assistant.
The changes preserve the achromatic design language while giving reading
more room, removing repeated explanatory copy, and keeping drafts and
keyboard focus stable through navigation and delayed responses.

Scope: `web/` only. The running research backend and its files are read-only.
An existing alarm process was verified alive, due 2026-09-08 09:41:46 +08:00.

Screenshots and transient inspection output live in `web/.shots/`.

## Implemented during the review

- Layout follows the space a panel actually has. Task navigation becomes a
  compact selector; Workspace rails and editor/preview panes stack; the
  Assistant leaves room to read and docks below content on phones. Sky goal
  panels and discussion sidebars follow their own available width.
  Before the first document opens, a narrow Workspace gives the available
  space to choosing a file rather than repeating an empty-editor instruction.
- Shared windows have dialog semantics, contained keyboard focus, an always
  visible close control, and return focus to their opener. Menus dismiss before
  their containing window, support Home/End, and return focus after dismissal.
- Workspace distinguishes loading, unavailable, empty, and filtered file lists.
  Search can be cleared; failed reads can be retried. Closing tabs and folding
  the file list keep keyboard focus useful; closed tabs keep unsaved drafts.
- Document and task-instruction drafts survive section changes. A save clears
  only the submitted snapshot; later writing remains dirty, including an undo
  during a pending save. Completed writes reach the currently mounted editor,
  preserve focus, and do not flash old text during a delayed refresh. The reload
  guard covers drafts even while another section is open.
- Inline file operations return focus on cancellation. Failed clipboard writes
  offer a selected path for manual copying instead of falsely saying "copied".
- Clean prose previews no longer repeat a success sentence. Formatting reports
  identify the source line only when needed. TeX delimiters inside inline code
  remain literal; the renderer and report recognize the same formula forms.
  Formulas include MathML, and refused formulas fall back to plain source.
  Display equations and table cells protect embedded math and literal code.
  TeX renders accept only the latest request and mark changes since the render.
- Settings starts with Appearance. Model roles and usage details are quieter;
  advanced controls fit narrow windows and use human labels. Save appears when
  something changed. Failed model discovery can be retried.
- Task reading links take less space above the question. Standing instructions
  use the same name on creation and editing forms. New task cancellation returns
  to its project; paper controls fit narrow reading areas.
- Amendment drafts survive switching between editing and diff views, and
  acceptance submits the reviewed text. Failed decision checks remain visible.
- Timeline paging stops at the last page and offers recovery after a failed
  page. Event details work from the keyboard and use the full width on phones.
- Assistant reads are tied to the selected conversation. Late replies do not
  overwrite another project's transcript; a continuing answer names its origin.
  Reading failures offer retry. Enter obeys the same availability rules as Send,
  and repeated Enter during session creation sends once. Editing a question is
  reachable by keyboard; an empty re-ask keeps the editor open.
  Long conversation lists scroll independently and preserve the composer.
- Creation forms retain their values after a failure and hold submitted fields
  while a request runs. Project names and descriptions have accessible labels.
  Touchscreens can reach project maintenance controls without hover.

## Backend limitation handled in the frontend

The current project rename endpoint updates database names without moving
`Problems/<project>/_docs` (`Tooling/state/projects.py` and `project_docs.py`,
read only). The rename window now checks the document listing and refuses a
rename when files or drafts would be stranded. Empty document shelves remain
renameable. No backend migration was attempted.

## Final verification

- TypeScript and production build passed after the final edits (09:36).
  The unit suite passed, 25 files / 483 tests. Lint passed with 12 Fast Refresh
  export warnings (11 existing,
  one from the shared math parser). The existing large-bundle warning remains.
- Browser checks cover the interactions above with deterministic API fixtures;
  all mutations in those tests are mocked. Live visual inspection blocks every
  non-GET API request, including model discovery.
- Dark/light screenshots cover primary routes at 390, 768, and 1440 px. Expanded
  parameters, model menus, and event details were also inspected at 320 px.
- Final full smoke suite: 90 passed / 2 conditional skips (09:36).
- Small-height inspection also covers 320 × 568 and 844 × 390. Live worker
  cards were checked after their changing content exposed an 11 px overflow;
  the grid now keeps a zero minimum track and wraps its metadata.
- The isolated Vite preview was restarted after a cached module missed a file
  change. Subsequent complete checks ran against the fresh preview.
- Final source check compared the preview's source maps with all 35 modified
  production TypeScript modules: no mismatches (09:39).

The alarm process exited successfully at 09:41:46 +08:00 after invoking its
sound. The existing research backend was not restarted or written to. The
isolated frontend preview on port 5174 was stopped at the end of the review.
