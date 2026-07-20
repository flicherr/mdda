from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.build import StateArtifacts
from orchestrator.manifest import load_scenario
from orchestrator.model import CommandResult, Toolchain
from orchestrator.pipeline import run_scenario


ROOT = Path(__file__).resolve().parents[1]


def declaration() -> dict:
    return {
        "stable_id": "usr:compute",
        "usr": "compute",
        "structural_key": "Provider|FunctionDecl|compute|int (int)|0",
        "kind": "FunctionDecl",
        "qualified_name": "compute",
        "owning_module": "Provider",
        "exported": True,
        "normalized": {"kind": "FunctionDecl", "canonical_type": "int (int)"},
    }


def success() -> CommandResult:
    return CommandResult(
        argv=("fake",),
        cwd="/tmp",
        returncode=0,
        stdout="",
        stderr="",
        duration_ms=1,
    )


class PipelineOrderTests(unittest.TestCase):
    def test_prediction_exists_before_after_consumer_oracle(self) -> None:
        scenario = load_scenario(
            ROOT / "scenarios/direct_and_controls/comment_only/scenario.json"
        )
        toolchain = Toolchain(
            schema_version=1,
            clangxx="fake-clang",
            analyzer=Path("/fake/analyzer"),
            required_clang_version="22.1.8",
            cxx_standard="c++20",
            bmi_mode="full",
            target=None,
            extra_compile_flags=(),
            extra_analyzer_flags=(),
            environment={},
            config_path=Path("/fake/config.json"),
        )
        provider_scan = {
            "schema_version": 1,
            "declarations": [declaration()],
            "imports": [],
        }

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)

            def fake_prepare(*args, **kwargs):
                state_name = args[1]
                directory = args[3]
                directory.mkdir(parents=True, exist_ok=True)
                return StateArtifacts(
                    state=state_name,
                    directory=directory,
                    pcm_files={},
                    module_scans={"Provider": provider_scan},
                )

            def fake_analyze(
                scenario_arg, state, artifacts, toolchain_arg, command_runner
            ):
                if artifacts.state == "after":
                    self.assertTrue(
                        (output / scenario.scenario_id / "prediction.json").is_file()
                    )
                artifacts.consumer_compile = success()
                artifacts.consumer_scan = {
                    "schema_version": 1,
                    "uses": [{"declaration": declaration()}],
                    "probes": [
                        {
                            "id": "result",
                            "selected_declaration": declaration(),
                        }
                    ],
                }

            with patch("orchestrator.pipeline.prepare_state", side_effect=fake_prepare), patch(
                "orchestrator.pipeline.analyze_consumer", side_effect=fake_analyze
            ):
                result = run_scenario(
                    scenario,
                    toolchain,
                    output,
                    {"clang_major": 22},
                )

            self.assertEqual("completed", result["status"])
            self.assertTrue(result["prediction_written_before_oracle"])
            self.assertFalse(result["observation"]["changed"])


if __name__ == "__main__":
    unittest.main()
