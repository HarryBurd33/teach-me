# Browser acceptance construction

Four frozen Playwright tests per matrix job cover real draft download/check/apply and original-byte preservation; metadata and jointpremises; undo/redo branching, reset and import; atomic malformed/duplicate/wrongbase/metadata/dangling/oversized refusal;20step historyeviction; keyboard-only creation/deletion/error/import/reset/export;390px layout; hostilelabels; fileURL opening; browser pageerrors/dialogs and non-file/blob requests. Generated fixtures use canonical temporary paths, and Python is selected portably through the CI environment.

The developer-only dependency is exactpinned @playwright/test1.64.1 with generated integrity lock. Official npm metadata supplied the version. Official setup-node v6 was resolved to immutable249970729cb0ef3589644e2896645e5dc5ba9c38. Existing pinned checkout/setup-python actions were reused. No testartifact upload service/action was added. The matrix is LinuxChromium/Firefox/WebKit andWindowsChromium.

Executed: both JavaScript syntax checks passed; npm ci --ignore-scripts succeeded; playwright test --list discovered12tests across3browserprojects. The WindowsChromium CI job adds another4executions, for16expectedremote executions. Tests and workflow hashes were frozen before candidate inspection, and still match. Browser binaries were neither installed nor launched locally. Worker-created node_modules were removed after discovery.

Actual remote CI and product acceptance remain parent gates. No skipped tests, retries or softened assertions are configured. A PlaywrightWebKit pass does not establish Safari qualification. This suite does not establish screenreader accessibility, learner efficacy, whole-skillWindows compatibility or hostile-filesystem containment.
