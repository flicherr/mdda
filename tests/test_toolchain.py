from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from orchestrator.build import _base_flags
from orchestrator.errors import ToolchainError
from orchestrator.model import Toolchain
from orchestrator.toolchain import _clang_version_tuple, doctor, load_toolchain


ROOT = Path(__file__).resolve().parents[1]


def toolchain(*, bmi_mode: str) -> Toolchain:
    return Toolchain(
        schema_version=1,
        clangxx="clang++-22",
        analyzer=Path("/tmp/manalyzer"),
        required_clang_version="22.1.8",
        cxx_standard="c++20",
        bmi_mode=bmi_mode,
        target=None,
        extra_compile_flags=(),
        extra_analyzer_flags=(),
        environment={},
        config_path=Path("/tmp/toolchain.json"),
    )


class ToolchainTests(unittest.TestCase):
    def test_example_pins_clang_22_1_8_and_full_bmi(self) -> None:
        value = load_toolchain(ROOT / "environment/toolchain.example.json")
        self.assertEqual("22.1.8", value.required_clang_version)
        self.assertEqual("full", value.bmi_mode)

    def test_parses_distribution_prefixed_clang_version(self) -> None:
        self.assertEqual(
            (22, 1, 8),
            _clang_version_tuple(
                "Ubuntu clang version 22.1.8 (++20260613092238+release)"
            ),
        )

    def test_bmi_mode_is_explicit_in_compiler_flags(self) -> None:
        cache = Path("/tmp/module-cache")
        self.assertIn(
            "-fno-modules-reduced-bmi",
            _base_flags(toolchain(bmi_mode="full"), cache),
        )
        self.assertIn(
            "-fmodules-reduced-bmi",
            _base_flags(toolchain(bmi_mode="reduced"), cache),
        )

    def test_doctor_rejects_a_different_patch_release(self) -> None:
        with TemporaryDirectory() as temporary:
            analyzer = Path(temporary) / "manalyzer"
            analyzer.touch(mode=0o755)
            value = replace(toolchain(bmi_mode="full"), analyzer=analyzer)
            with patch(
                "orchestrator.toolchain.shutil.which", return_value="/fake/clang++"
            ), patch(
                "orchestrator.toolchain._version",
                side_effect=[
                    "clang version 22.1.9",
                    "manalyzer 0.4.0\nclang version 22.1.8",
                ],
            ):
                with self.assertRaises(ToolchainError):
                    doctor(value)


if __name__ == "__main__":
    unittest.main()
