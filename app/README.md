# Desktop App Wrapper

This folder stores the source files used by the local macOS wrapper.

The canonical backend lives in the `src/infra_ingest/` package, with `main.py`
kept at the repository root as a thin compatibility launcher:

- `main.py`
- `src/infra_ingest/cli.py`
- `src/infra_ingest/config.py`
- `src/infra_ingest/converters.py`
- `src/infra_ingest/document_parser.py`
- `src/infra_ingest/pipeline.py`
- `src/infra_ingest/sources.py`
- `src/infra_ingest/llm_client.py`
- `src/infra_ingest/note_writer.py`
- `src/infra_ingest/prompts.py`
- `src/infra_ingest/structured_note.py`
- `src/infra_ingest/glossary.py`
- `src/infra_ingest/finance.py`
- `src/infra_ingest/entities.py`
- `src/infra_ingest/library.py`
- `src/infra_ingest/graph.py`
- `src/infra_ingest/raw_archive.py`
- `src/infra_ingest/material_parser.py`
- `src/infra_ingest/rag.py`
- `src/infra_ingest/transcript.py`
- `src/infra_ingest/transcriber.py`

Use `scripts/sync_app.sh` to copy the current backend and wrapper files into:

```text
/Applications/Whisper转写.app
```

Do not edit files directly inside `/Applications/Whisper转写.app` unless you are debugging a packaged build.

## Local UI Preview

Open the static HTML preview in a browser:

```bash
open app/ui_preview.html
```

Run the Tk desktop UI from the repository:

```bash
python3 app/whisper_gui.py
```

The desktop UI now exposes the main research workflow:

- URL or local file input
- output directory and note title
- Whisper model, language, and material type
- glossary file
- local price/financial CSV inputs
- event date and benchmark ticker for the event-study backtest
- optional LLM structured-note settings
