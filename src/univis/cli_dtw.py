"""Command-line DTW quality checks for UniVis datasets."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Sequence

from univis.core.components import ComponentBundle, ComponentNameResolver
from univis.core.episode_session import EpisodeSession
from univis.formats import load_format_components
from univis.quality.dtw import DTWTrajectoryQualityBackend
from univis.quality.dtw.visualization import DTWComparisonPlotter
from univis.quality.service import QualityService
from univis.utils.json_io import write_json


DEFAULT_INPUT_FORMAT = "PikaRawEpisodeAdapter"


class DTWCLI:
    """Small CLI wrapper around the same DTW service used by the GUI."""

    def __init__(self, components: ComponentBundle | None = None) -> None:
        """Initialize reusable CLI component registries.

        Inputs:
            components: Optional format components for tests.
        Output:
            CLI object with case-insensitive component alias resolvers.
        """

        self.components = components or load_format_components()
        self.input_resolver = ComponentNameResolver(
            self.components.input_adapters,
            "input format",
        )

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Parse arguments, run the selected DTW command, and print outputs.

        Inputs:
            argv: Optional command-line argument sequence without program name.
        Output:
            Process-style return code.
        """

        parser = self._parser()
        args = parser.parse_args(argv)
        if args.command == "compare":
            paths = self._run_with_parser(parser, self._run_compare, args)
        elif args.command == "stats":
            paths = self._run_with_parser(parser, self._run_stats, args)
        else:
            raise ValueError(f"unknown command: {args.command}")
        for path in paths:
            print(path)
        return 0

    def _run_compare(self, args: argparse.Namespace) -> list[Path]:
        """Run one current-vs-reference DTW comparison."""

        service = self._service(args.input_format, args.source)
        comparison = service.compare(args.current, args.reference, args.backend)
        output_dir = self._output_dir(args.output, args.source, "compare")
        stem = self._compare_stem(args.current, args.reference)
        json_path = output_dir / f"{stem}.json"
        png_path = output_dir / f"{stem}.png"
        write_json(json_path, comparison.model_dump())
        DTWComparisonPlotter().render_png(
            service.load_episode(args.current),
            service.load_episode(args.reference),
            comparison,
            png_path,
        )
        return [json_path, png_path]

    def _run_stats(self, args: argparse.Namespace) -> list[Path]:
        """Run selected/all episode DTW statistics against one reference."""

        service = self._service(args.input_format, args.source)
        episode_ids = self._stats_episode_ids(service, args)
        stats = service.selected_stats(args.reference, episode_ids, args.backend)
        output_dir = self._output_dir(args.output, args.source, "stats")
        json_path = output_dir / f"{self._stats_stem(args.reference)}.json"
        write_json(json_path, stats.model_dump())
        return [json_path]

    def _service(self, input_format: str, source: str) -> QualityService:
        """Create a service bound to a source path without full validation.

        Inputs:
            input_format: Registered adapter name.
            source: Local file or directory path readable by the adapter.
        Output:
            QualityService using the requested active source.
        """

        resolved = self.input_resolver.resolve(input_format)
        session = EpisodeSession(self.components.input_adapters, resolved)
        session.set_source(resolved, source, validate=False)
        return QualityService(session, [DTWTrajectoryQualityBackend()])

    def _run_with_parser(self, parser, func, args: argparse.Namespace) -> list[Path]:
        """Run a subcommand and print resolver errors with candidates."""

        try:
            return func(args)
        except ValueError as exc:
            parser.error(str(exc))

    def _stats_episode_ids(self, service: QualityService, args: argparse.Namespace) -> list[str]:
        """Resolve explicit or all active-source episode ids for stats."""

        if args.all:
            return [episode_id for episode_id in service.list_episode_ids() if episode_id != args.reference]
        if args.episodes:
            return list(args.episodes)
        raise ValueError("stats requires --all or --episodes")

    def _output_dir(self, output: str | None, source: str, kind: str) -> Path:
        """Resolve the destination directory for a DTW command."""

        if output:
            return Path(output).expanduser()
        source_path = Path(source).expanduser()
        root = source_path if source_path.is_dir() else source_path.parent
        return root / "dtw" / kind

    def _compare_stem(self, current: str, reference: str) -> str:
        """Return a timestamped filename stem for compare outputs."""

        return f"compare_{self._safe(current)}_vs_{self._safe(reference)}_{self._timestamp()}"

    def _stats_stem(self, reference: str) -> str:
        """Return a timestamped filename stem for stats outputs."""

        return f"stats_{self._safe(reference)}_{self._timestamp()}"

    def _timestamp(self) -> str:
        """Return a compact local timestamp for output filenames."""

        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _safe(self, value: str) -> str:
        """Make an episode id safe enough for filenames."""

        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "episode"

    def _parser(self) -> argparse.ArgumentParser:
        """Build the DTW CLI argument parser."""

        parser = argparse.ArgumentParser(description="Run UniVis DTW quality checks.")
        subparsers = parser.add_subparsers(dest="command", required=True)
        self._add_compare_parser(subparsers)
        self._add_stats_parser(subparsers)
        return parser

    def _add_common(self, parser: argparse.ArgumentParser) -> None:
        """Register arguments shared by compare and stats."""

        parser.add_argument("--source", required=True, help="Input dataset directory or file.")
        parser.add_argument(
            "--input-format",
            "--if",
            default=DEFAULT_INPUT_FORMAT,
            help="Registered input adapter name or alias.",
        )
        parser.add_argument("--backend", default="DTWTrajectoryQualityBackend", help="Registered quality backend name.")
        parser.add_argument("--output", default="", help="Output directory. Defaults to <source>/dtw/<command>.")

    def _add_compare_parser(self, subparsers) -> None:
        """Register the compare subcommand."""

        parser = subparsers.add_parser("compare", help="Compare two episodes and export JSON plus PNG.")
        self._add_common(parser)
        parser.add_argument("--current", required=True, help="Episode id to evaluate.")
        parser.add_argument("--reference", required=True, help="Reference episode id.")

    def _add_stats_parser(self, subparsers) -> None:
        """Register the stats subcommand."""

        parser = subparsers.add_parser("stats", help="Aggregate episodes against one reference.")
        self._add_common(parser)
        parser.add_argument("--reference", required=True, help="Reference episode id.")
        parser.add_argument("--all", action="store_true", help="Use all episodes except the reference.")
        parser.add_argument("--episodes", nargs="*", default=[], help="Explicit episode ids to evaluate.")


def main() -> None:
    """Console-script entrypoint for `univis-dtw`."""

    raise SystemExit(DTWCLI().run())


if __name__ == "__main__":
    main()
