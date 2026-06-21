"""Core pipeline orchestration for infra-ingest."""

import os
import tempfile
from datetime import datetime
from pathlib import Path

from .backtest import run_event_study, write_backtest_result
from .config import load_environment, resolve_env_path, resolve_vault_path
from .converters import AUDIO_VIDEO_EXTENSIONS
from .document_parser import extract_document_text
from .entities import extract_entities
from .finance import (
    extract_financial_entities,
    load_market_data_summary,
    merge_financial_entities,
    render_quant_research_section,
)
from .glossary import load_glossary, merge_initial_prompt
from .graph import update_graph_from_note
from .library import DEFAULT_LIBRARY_DB, index_note_file
from .llm_client import build_llm_config_from_env, call_llm_api
from .manifest import build_manifest, sha256_file, write_manifest
from .material_parser import parse_material_sections
from .note_writer import (
    build_note_metadata,
    generate_basic_note,
    generate_source_note,
    resolve_target_dir,
    write_note,
)
from .prompts import build_chunk_summary_prompt, build_system_prompt
from .raw_archive import archive_source
from .research_runs import record_research_run
from .sources import download_audio_from_url, is_url, title_from_url
from .structured_note import parse_note_json, render_structured_note_markdown
from .transcript import write_segments
from .transcriber import transcribe_audio


def run_pipeline(args, console, script_dir=None):
    """Run the ingest pipeline for parsed CLI arguments."""
    started_at = datetime.now()
    project_dir = Path(script_dir or Path(__file__).resolve().parent)
    env_file = resolve_env_path(args.env, project_dir)
    load_environment(env_file)

    llm_config = build_llm_config_from_env()
    use_llm = not args.no_llm and bool(llm_config.get("api_key"))
    glossary_terms = load_glossary(getattr(args, "glossary_file", None))
    data_summary = load_market_data_summary(
        getattr(args, "price_data_csv", None),
        getattr(args, "financial_data_csv", None),
    )

    vault_path, vault_mode = resolve_vault_path(project_dir)
    if vault_mode == "discovered":
        console.log(f"[green]自动寻找到 Obsidian 库根目录: {vault_path}[/green]")
    elif vault_mode == "fallback":
        console.log(f"[yellow]未找到 Obsidian 库，改写入普通 Markdown 输出目录: {vault_path}[/yellow]")

    input_ref = args.input.strip()
    input_is_url = is_url(input_ref)
    temp_dir = None

    try:
        if input_is_url:
            temp_dir = tempfile.TemporaryDirectory(prefix="infra_ingest_url_")
            audio_path = download_audio_from_url(
                input_ref,
                temp_dir.name,
                cookies_browser=args.cookies_browser,
                cookies_file=args.cookies_file,
                logger=lambda msg: console.log(f"[yellow]{msg}[/yellow]"),
            )
            input_path = str(audio_path)
        else:
            input_path = str(Path(input_ref).expanduser().resolve())
            if not Path(input_path).exists():
                raise RuntimeError(f"错误: 输入文件不存在: {input_path}")

        base_name = title_from_url(input_ref) if input_is_url else Path(input_path).stem
        file_ext = Path(input_path).suffix.lower()
        title = args.title or base_name
        source = args.source or (input_ref if input_is_url else Path(input_path).name)
        file_hash = sha256_file(input_path)
        library_db = getattr(args, "library_db", DEFAULT_LIBRARY_DB)
        raw_archive_path = None
        if not getattr(args, "no_archive", False):
            raw_archive_path = archive_source(input_path, file_hash, library_db)

        raw_text, transcription = extract_raw_text(input_path, file_ext, args, console, glossary_terms)
        if not raw_text.strip():
            raise RuntimeError("错误: 提取出的内容为空！")
        rule_finance_entities = extract_financial_entities(raw_text, glossary_terms)
        material_sections = parse_material_sections(raw_text, getattr(args, "material_type", "auto"))
        backtest_result = run_event_study(
            getattr(args, "price_data_csv", None),
            rule_finance_entities["tickers"],
            event_date=getattr(args, "event_date", None),
            benchmark_ticker=getattr(args, "benchmark_ticker", None),
        )
        entities = list(
            dict.fromkeys(
                extract_entities(raw_text, glossary_terms)
                + rule_finance_entities["companies"]
                + rule_finance_entities["tickers"]
                + rule_finance_entities["industries"]
                + rule_finance_entities["metrics"]
                + rule_finance_entities["factors"]
            )
        )
        companies = list(dict.fromkeys((getattr(args, "company", None) or []) + rule_finance_entities["companies"]))
        industries = list(dict.fromkeys((getattr(args, "industry", None) or []) + rule_finance_entities["industries"]))
        metadata = build_note_metadata(
            title=title,
            author=args.author,
            source=source,
            mode="structured" if use_llm else "basic",
            material_type=getattr(args, "material_type", "auto"),
            source_type="url" if input_is_url else "file",
            companies=companies,
            tickers=rule_finance_entities["tickers"],
            industries=industries,
            metrics=rule_finance_entities["metrics"],
            factors=rule_finance_entities["factors"],
            risk_events=rule_finance_entities["risk_events"],
            entities=entities,
            now=started_at,
        )

        final_note_content = build_note_content(
            raw_text=raw_text,
            title=title,
            author=args.author,
            source=source,
            metadata=metadata,
            entities=entities,
            finance_entities=rule_finance_entities,
            data_summary=data_summary,
            material_sections=material_sections,
            backtest_result=backtest_result,
            use_llm=use_llm,
            llm_config=llm_config,
            material_type=getattr(args, "material_type", "auto"),
            glossary_terms=glossary_terms,
            console=console,
        )

        target_dir = resolve_target_dir(
            args.output_dir,
            vault_path,
            default_folder=os.getenv("TARGET_FOLDER", "Clippings"),
        )
        target_file_path = write_note(target_dir, title, final_note_content)
        backtest_path = write_backtest_result(target_file_path, backtest_result)
        if not getattr(args, "no_index", False):
            index_note_file(library_db, target_file_path, glossary_terms)
            graph_path = update_graph_from_note(library_db, target_file_path, glossary_terms)
        else:
            graph_path = None
        segments_path = write_segments(target_file_path, transcription)
        manifest = build_manifest(
            input_ref=input_ref,
            input_path=input_path,
            input_is_url=input_is_url,
            file_hash=file_hash,
            raw_archive_path=raw_archive_path,
            output_path=target_file_path,
            segments_path=segments_path,
            graph_path=graph_path,
            backtest_path=backtest_path,
            backtest_result=backtest_result,
            data_summary=data_summary,
            llm_config=llm_config if use_llm else None,
            args=args,
            started_at=started_at,
        )
        manifest_path = write_manifest(target_file_path, manifest)
        if not getattr(args, "no_index", False):
            record_research_run(
                library_db,
                note_path=target_file_path,
                manifest_path=manifest_path,
                input_ref=input_ref,
                event_date=getattr(args, "event_date", None),
                tickers=rule_finance_entities["tickers"],
                metrics=rule_finance_entities["metrics"],
                factors=rule_finance_entities["factors"],
                backtest_result=backtest_result,
            )
        console.print(f"[green]🎉 成功写入笔记: {target_file_path}[/green]")
        console.print(f"[green]🧾 处理清单已写入: {manifest_path}[/green]")
        return target_file_path
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def extract_raw_text(input_path, file_ext, args, console, glossary_terms=None):
    """Route an input path to transcription or document extraction."""
    if file_ext in AUDIO_VIDEO_EXTENSIONS:
        whisper_language = args.language or os.getenv("WHISPER_LANGUAGE") or None
        whisper_beam_size = args.beam_size or int(os.getenv("WHISPER_BEAM_SIZE", "5"))
        configured_prompt = args.initial_prompt or os.getenv("WHISPER_INITIAL_PROMPT") or None
        whisper_initial_prompt = merge_initial_prompt(configured_prompt, glossary_terms or [])
        whisper_device = args.device or os.getenv("WHISPER_DEVICE", "cpu")
        whisper_compute_type = args.compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        transcription = transcribe_audio(
            input_path,
            model_size=args.model,
            language=whisper_language,
            beam_size=whisper_beam_size,
            vad_filter=not args.no_vad,
            initial_prompt=whisper_initial_prompt,
            device=whisper_device,
            compute_type=whisper_compute_type,
            console=console,
        )
        return transcription["text"], transcription

    return extract_document_text(input_path, file_ext, console), None


def build_note_content(
    raw_text,
    title,
    author,
    source,
    metadata,
    entities,
    finance_entities,
    data_summary,
    material_sections,
    backtest_result,
    use_llm,
    llm_config,
    material_type,
    glossary_terms,
    console,
):
    """Generate final Markdown content, with or without LLM structuring."""
    if use_llm:
        console.log(
            f"[yellow]正在调用 LLM API: {llm_config['base_url'].rstrip('/')}/chat/completions "
            f"(model={llm_config['model']})[/yellow]"
        )
        structured_note = build_llm_output(raw_text, llm_config, console, material_type, glossary_terms)
        merged_finance_entities = merge_financial_entities(
            finance_entities,
            structured_note.get("financial_entities"),
        )
        llm_output = "\n\n".join(
            [
                render_structured_note_markdown(structured_note),
                render_quant_research_section(
                    merged_finance_entities,
                    note=structured_note,
                    data_summary=data_summary,
                    material_sections=material_sections,
                    material_type=material_type,
                    backtest_result=backtest_result,
                ),
            ]
        )
        console.log("[green]大模型知识萃取成功！[/green]")
        return generate_source_note(title, author, source, llm_output, metadata=metadata, entities=entities)

    console.log("[yellow]未启用 LLM，生成基础 Markdown 笔记。[/yellow]")
    basic_note = generate_basic_note(title, author, source, raw_text, metadata=metadata, entities=entities)
    return "\n\n".join(
        [
            basic_note,
            render_quant_research_section(
                finance_entities,
                data_summary=data_summary,
                material_sections=material_sections,
                material_type=material_type,
                backtest_result=backtest_result,
            ),
        ]
    )


def build_llm_output(raw_text, llm_config, console, material_type="auto", glossary_terms=None):
    """Generate LLM output directly or through chunk summaries for long text."""
    chunk_limit = int(os.getenv("LLM_CHUNK_CHAR_LIMIT", "60000"))
    chunk_overlap = int(os.getenv("LLM_CHUNK_OVERLAP", "800"))
    chunks = split_text(raw_text, chunk_limit, chunk_overlap)
    system_prompt = build_system_prompt(material_type, glossary_terms)
    if len(chunks) == 1:
        return parse_note_json(call_llm_api(raw_text, system_prompt, llm_config))

    console.log(f"[yellow]文本较长，拆成 {len(chunks)} 个分块先摘要，再合并生成最终笔记。[/yellow]")
    chunk_summaries = []
    chunk_prompt = build_chunk_summary_prompt(material_type, glossary_terms)
    for index, chunk in enumerate(chunks, start=1):
        console.log(f"[yellow]正在处理长文本分块 {index}/{len(chunks)}[/yellow]")
        chunk_payload = f"分块 {index}/{len(chunks)}：\n---\n{chunk}\n---"
        summary = call_llm_api(chunk_payload, chunk_prompt, llm_config)
        chunk_summaries.append(f"## 分块 {index}/{len(chunks)} 摘要\n\n{summary}")

    combined = "\n\n".join(chunk_summaries)
    synthesis_payload = (
        "以下是一份长资料按顺序生成的分块摘要。请把它们合并成一篇完整的结构化投研笔记，"
        "避免重复，保留关键来源线索。\n---\n"
        f"{combined}\n---"
    )
    return parse_note_json(call_llm_api(synthesis_payload, system_prompt, llm_config))


def split_text(text, chunk_size, overlap=0):
    """Split text into overlapping chunks without dropping content."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    length = len(text)
    overlap = max(0, min(overlap, chunk_size - 1))

    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        if end == length:
            break
        start = end - overlap

    return chunks
