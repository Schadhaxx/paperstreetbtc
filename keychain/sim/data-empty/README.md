# data-empty/ — edge-case-test fail mode
Intentionally contains NO fetch data (.json/.txt) and NO fonts
(.vlw), so every fetch and every font load fails. The test refuses
to run fail mode against a dir containing any of those files.
Run: `edge-case-test data-empty fail data`
