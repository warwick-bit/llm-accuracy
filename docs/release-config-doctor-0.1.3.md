# Config Doctor 0.1.3 preview

Choose what you want checked; Doctor now finds the relevant files for you within
that setup. It no longer asks you to supply configuration paths or build a file
list as the normal starting step. It asks again only for a meaningful choice,
such as which setup you mean or whether to include an additional folder.

Collection stays within the selected profile, relevant installed add-ons and any
chosen project. Messages, credentials, unrelated files and other profiles remain
excluded. Doctor does not run the files it reviews or connect to external tools.
If you supply an explicit file list, it keeps that narrower boundary.

The agent builds the existing file list for the audit tool. The tool still reads
only listed files; no new collector, schema, dependency or plugin change is added.
Reviewing all listed files does not prove the whole setup was covered or that its
rules are followed. Missing evidence remains visible.

Use the [startup guide](../tools/config-doctor/README.md) or
[0.1.3 preview release](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.3).
Python 3.11+ is required. Previous release assets remain unchanged.

Qualification uses the existing Doctor contracts, archive/source and link checks,
a bounded synthetic collection screen, independent review and required CI.
See the published release for completed results and limits. These checks do not
establish reliable collection or safe operation in every real installation.
