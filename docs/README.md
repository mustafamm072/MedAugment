# Documentation

MedAugmentX docs are organized for quick adoption first, deeper reference
second.

| Document | Start here when you need |
| --- | --- |
| [Research guide](RESEARCH_GUIDE.md) | Replay, worker seeds, evaluation reporting, and software citation |
| [Commercial adoption](COMMERCIAL_ADOPTION.md) | Production-readiness checklist, intended use, validation, audit trail, privacy, and dependency guidance |
| [API examples](API_EXAMPLES.md) | Practical snippets for common workflows |
| [API reference](API_REFERENCE.md) | Supported public imports, constructor summaries, and optional extras |
| [Architecture](ARCHITECTURE.md) | Layering, dependency boundaries, transform contracts, and testing strategy |
| [Milestones](MILESTONES.md) | Roadmap, release phases, and v1.0 acceptance criteria |
| [Security policy](../SECURITY.md) | Vulnerability reporting, PHI handling, and dependency posture |

For a first integration, read the main [README](../README.md), then the
[Commercial adoption](COMMERCIAL_ADOPTION.md) checklist, then the examples for
your framework or modality.

## Build the searchable documentation

From the repository root:

```bash
pip install ".[docs]"
python -m sphinx -W --keep-going -b html -c docs/sphinx . /tmp/medaugmentx-docs
```

Open `/tmp/medaugmentx-docs/docs/sphinx/index.html`. The site uses the existing
Markdown guides as its source. CI builds it and uploads a preview artifact;
public hosting is not configured by this change.
