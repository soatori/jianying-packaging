#!/usr/bin/env python3
"""Packaging analysis and schema 2.0 prepare/commit CLI.

Analysis and preparation are read-only with respect to drafts. Commit uses the
existing jianying-editor transaction API on a prepared candidate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from packaging_tools.io import BlockedReportError, dump_json, load_json, text_result, unwrap_report, write_json
from packaging_tools.inventory import inventory_templates_and_materials
from packaging_tools.audio_inventory import classify_audio_events
from packaging_tools.draft_apply import (
    commit_prepared_packaging,
    prepare_packaging_plan,
    resolve_prepared_path,
)
from packaging_tools.layer_discovery import discover_packaging_layers
from packaging_tools.learning import build_learning_report, validate_learning_report
from packaging_tools.motion_check import check_motion_reuse
from packaging_tools.layout_resolver import resolve_relative_layout
from packaging_tools.reference_diff import diff_manual_reference
from packaging_tools.result import exit_code, result
from packaging_tools.snapshot import build_packaging_snapshot
from packaging_tools.sound_check import check_sound_operations
from packaging_tools.subtitle_resolver import resolve_subtitle_anchor, resolve_text_hashes
from packaging_tools.text_ops import check_text_replacement
from packaging_tools.validators import (
    check_generic_content,
    validate_layout_registry,
    validate_plan,
    validate_sound_catalog,
)
from packaging_tools.verification import verify_packaging_result


def _editor_root(value: str | None) -> Path:
    if value:
        return Path(value)
    env = os.environ.get("JIANYING_EDITOR_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "jianying-editor-skill"


def _run(args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "validate":
        if args.kind == "plan":
            catalog = unwrap_report(load_json(args.catalog)) if args.catalog else None
            pools = unwrap_report(load_json(args.pools)) if args.pools else None
            report = validate_plan(
                unwrap_report(load_json(args.path)),
                sound_catalog=catalog,
                sound_pools=pools,
            )
            return result("packaging_plan_validation", data=report, errors=report.get("errors", []), warnings=report.get("warnings", []))
        if args.kind == "layout":
            report = validate_layout_registry(unwrap_report(load_json(args.path)))
            return result("packaging_layout_validation", data=report, errors=report.get("errors", []), warnings=report.get("warnings", []))
        if args.kind == "sound":
            pools = unwrap_report(load_json(args.pools)) if args.pools else None
            report = validate_sound_catalog(unwrap_report(load_json(args.path)), pools)
            return result("packaging_sound_catalog_validation", data=report, errors=report.get("errors", []), warnings=report.get("warnings", []))
        if args.kind == "learning":
            report = validate_learning_report(unwrap_report(load_json(args.path)))
            return result("learning_report_validation", data=report, errors=report.get("errors", []), input_errors=report.get("input_errors", []), warnings=report.get("warnings", []), summary=report.get("summary", {}))
        if args.kind == "generic":
            report = check_generic_content(args.paths, args.forbid)
            return result("packaging_generic_content_validation", data=report, errors=report.get("errors", []), input_errors=report.get("input_errors", []), warnings=report.get("warnings", []))
    if command == "prepare":
        plan = unwrap_report(load_json(args.plan))
        catalog = unwrap_report(load_json(args.catalog)) if args.catalog else None
        pools = unwrap_report(load_json(args.pools)) if args.pools else None
        animation_capabilities = unwrap_report(load_json(args.animation_capabilities)) if args.animation_capabilities else None
        existing_audio = unwrap_report(load_json(args.existing_audio)) if args.existing_audio else None
        return prepare_packaging_plan(
            plan,
            draft_path=args.draft,
            timeline=args.timeline,
            editor_root=_editor_root(args.editor_root),
            prepared_path=args.prepared,
            sound_catalog=catalog,
            sound_pools=pools,
            animation_cache_root=args.animation_cache_root,
            animation_capabilities=animation_capabilities,
            animation_version=args.animation_version,
            existing_audio=existing_audio,
        )
    if command == "commit":
        prepared_path = resolve_prepared_path(args.prepared)
        plan = unwrap_report(load_json(args.plan))
        prepared = load_json(prepared_path)
        return commit_prepared_packaging(
            plan,
            prepared,
            approved_prepared_hash=args.approved_prepared_hash,
            draft_path=args.draft,
            timeline=args.timeline,
            editor_root=_editor_root(args.editor_root),
            prepared_path=prepared_path,
        )
    if command == "snapshot":
        return build_packaging_snapshot(unwrap_report(load_json(args.observation)))
    if command == "diff":
        return diff_manual_reference(unwrap_report(load_json(args.current)), unwrap_report(load_json(args.reference)))
    if command == "inventory":
        return inventory_templates_and_materials(unwrap_report(load_json(args.observation)))
    if command == "layers":
        return discover_packaging_layers(unwrap_report(load_json(args.observation)))
    if command == "motion-check":
        return check_motion_reuse(unwrap_report(load_json(args.observation)), args.adjacent_window)
    if command == "audio-audit":
        return classify_audio_events(unwrap_report(load_json(args.observation)))
    if command == "resolve":
        plan = unwrap_report(load_json(args.plan))
        observation = unwrap_report(load_json(args.observation), "packaging_snapshot")
        anchor_report = resolve_subtitle_anchor(plan, observation)
        manifest = observation.get("subtitle_units", []) if isinstance(observation, dict) else []
        text_report = resolve_text_hashes(plan, manifest)
        layout_reports = []
        registry = unwrap_report(load_json(args.registry)) if args.registry else {"templates": []}
        resolved_by_group = (anchor_report.get("data") or {}).get("by_group", {}) if isinstance(anchor_report.get("data"), dict) else {}
        for group in plan.get("groups", []) if isinstance(plan, dict) else []:
            if not isinstance(group, dict) or not group.get("layout"):
                continue
            anchor_entry = resolved_by_group.get(str(group.get("id")), {})
            anchor = anchor_entry.get("runtime_anchor") if isinstance(anchor_entry, dict) else {}
            layout_reports.append(resolve_relative_layout(group, registry, anchor))
        errors = anchor_report.get("errors", []) + text_report.get("errors", [])
        errors.extend(error for report in layout_reports for error in report.get("errors", []))
        warnings = anchor_report.get("warnings", []) + text_report.get("warnings", [])
        return result("packaging_resolution", data={"subtitle": anchor_report, "text": text_report, "layouts": layout_reports}, errors=errors, warnings=warnings)
    if command == "sound-check":
        existing = unwrap_report(load_json(args.existing_audio)) if args.existing_audio else None
        return check_sound_operations(
            unwrap_report(load_json(args.plan)),
            unwrap_report(load_json(args.catalog)),
            unwrap_report(load_json(args.pools)),
            existing,
        )
    if command == "verify":
        return verify_packaging_result(
            unwrap_report(load_json(args.before), "packaging_snapshot"),
            unwrap_report(load_json(args.after), "packaging_snapshot"),
            unwrap_report(load_json(args.plan)),
        )
    if command == "text-check":
        return check_text_replacement(load_json(args.prototype), load_json(args.replacement))
    if command == "learning-report":
        entries = unwrap_report(load_json(args.entries))
        return build_learning_report(entries, source_kind=args.source_kind, case_ref=args.case_ref)
    raise ValueError(f"unsupported command: {command}")


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(f"argument error: {message}")


def _normalize_output_options(argv: list[str] | None) -> list[str] | None:
    """Allow output options before or after the subcommand."""
    if argv is None:
        return None
    leading: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"--format", "--out"} and index + 1 < len(argv):
            leading.extend((token, argv[index + 1]))
            index += 2
            continue
        if token.startswith("--format=") or token.startswith("--out="):
            leading.append(token)
            index += 1
            continue
        remaining.append(token)
        index += 1
    return leading + remaining


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--out", help="write the complete report to this path")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate_sub = validate.add_subparsers(dest="kind", required=True)
    for kind, help_text in (("plan", "validate a packaging plan"), ("layout", "validate a layout registry"), ("learning", "validate a learning report")):
        item = validate_sub.add_parser(kind, help=help_text)
        item.add_argument("path")
        if kind == "plan":
            item.add_argument("--catalog", help="project-specific sound catalog JSON")
            item.add_argument("--pools", help="project-specific motion sound pools JSON")
    sound = validate_sub.add_parser("sound", help="validate a sound catalog and optional pools")
    sound.add_argument("path")
    sound.add_argument("--pools")
    generic = validate_sub.add_parser("generic", help="scan generic skill content")
    generic.add_argument("paths", nargs="+")
    generic.add_argument("--forbid", action="append", default=[])

    prepare = sub.add_parser("prepare", help="validate a plan and persist its candidate without draft writes")
    prepare.add_argument("--draft", required=True)
    prepare.add_argument("--timeline", required=True, help="source timeline selector")
    prepare.add_argument("--plan", required=True)
    prepare.add_argument("--prepared", required=True, help="prepared artifact path under the skill temp directory")
    prepare.add_argument("--catalog", help="current case sound catalog JSON")
    prepare.add_argument("--pools", help="current case motion sound pools JSON")
    prepare.add_argument("--animation-cache-root", help="current Jianying User Data/Cache root")
    prepare.add_argument("--animation-capabilities", help="same-version, native-verified text animation capability JSON")
    prepare.add_argument("--animation-version", help="installed Jianying version if it cannot be read from the editor DLL")
    prepare.add_argument("--existing-audio", help="optional current audio/dialogue interval evidence JSON")
    prepare.add_argument("--editor-root", help="jianying-editor skill root")

    commit = sub.add_parser("commit", help="commit an approved, unchanged prepared artifact to a clone")
    commit.add_argument("--draft", required=True)
    commit.add_argument("--timeline", required=True, help="source timeline selector")
    commit.add_argument("--plan", required=True)
    commit.add_argument("--prepared", required=True, help="prepared artifact path under the skill temp directory")
    commit.add_argument("--approved-prepared-hash", required=True, help="exact prepared artifact hash approved for this commit")
    commit.add_argument("--editor-root", help="jianying-editor skill root")

    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--observation", required=True)
    diff = sub.add_parser("diff")
    diff.add_argument("--current", required=True)
    diff.add_argument("--reference", required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--observation", required=True)
    layers = sub.add_parser("layers")
    layers.add_argument("--observation", required=True)
    motion = sub.add_parser("motion-check")
    motion.add_argument("--observation", required=True)
    motion.add_argument("--adjacent-window", type=int, default=1)
    audio_audit = sub.add_parser("audio-audit")
    audio_audit.add_argument("--observation", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--plan", required=True)
    resolve.add_argument("--observation", required=True)
    resolve.add_argument("--registry")
    sound_check = sub.add_parser("sound-check")
    sound_check.add_argument("--plan", required=True)
    sound_check.add_argument("--catalog", required=True)
    sound_check.add_argument("--pools", required=True)
    sound_check.add_argument("--existing-audio")
    verify = sub.add_parser("verify")
    verify.add_argument("--before", required=True)
    verify.add_argument("--after", required=True)
    verify.add_argument("--plan", required=True)
    text_check = sub.add_parser("text-check")
    text_check.add_argument("--prototype", required=True)
    text_check.add_argument("--replacement", required=True)

    learning = sub.add_parser("learning-report")
    learning.add_argument("--entries", required=True)
    learning.add_argument("--source-kind", choices=("project_case", "synthetic_fixture", "manual_review"), default="project_case")
    learning.add_argument("--case-ref")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        raw_argv = sys.argv[1:] if argv is None else argv
        args = parser.parse_args(_normalize_output_options(raw_argv))
        path_error = None
        if args.command in {"prepare", "commit"}:
            preparing = args.command == "prepare"
            input_paths = [args.plan]
            if preparing:
                input_paths.extend(
                    value for value in (
                        args.catalog, args.pools, args.animation_capabilities, args.existing_audio,
                    ) if value
                )
            else:
                input_paths.append(args.prepared)
            resolved_inputs = {Path(value).expanduser().resolve() for value in input_paths}
            draft_root = Path(args.draft).expanduser().resolve()
            prepared_output = Path(args.prepared).expanduser().resolve() if preparing else None
            if preparing and prepared_output in resolved_inputs:
                path_error = "prepared output path conflicts with input file"
            if preparing and (prepared_output == draft_root or draft_root in prepared_output.parents):
                path_error = path_error or "prepared output path is inside draft root"
            report_output = getattr(args, "out", None)
            if report_output:
                resolved_report = Path(report_output).expanduser().resolve()
                report_inside_draft = resolved_report == draft_root or draft_root in resolved_report.parents
                if resolved_report in resolved_inputs or (preparing and resolved_report == prepared_output) or report_inside_draft:
                    path_error = path_error or (
                        "report output path is inside draft root"
                        if report_inside_draft
                        else "report output path conflicts with an input or prepared artifact"
                    )
                    args.out = None
        if path_error:
            report_type = "packaging_prepare" if args.command == "prepare" else "packaging_commit"
            report = result(report_type, input_errors=[path_error], status="blocked")
        else:
            report = _run(args)
    except BlockedReportError as exc:
        report = result("packaging_cli", errors=[f"blocked input report: {exc}"], status="blocked")
        code = 1
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        report = result("packaging_cli", input_errors=[f"input error: {type(exc).__name__}: {exc}"], status="blocked")
        code = 2
    else:
        code = exit_code(report)
    output_format = getattr(locals().get("args"), "format", "json")
    output_path = getattr(locals().get("args"), "out", None)
    if output_path:
        try:
            write_json(output_path, report)
        except OSError as exc:
            report = result("packaging_cli", data={"report": report}, input_errors=[f"output error: {exc}"], status="blocked")
            code = 2
            output_format = "json"
    print(text_result(report) if output_format == "text" else dump_json(report))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
