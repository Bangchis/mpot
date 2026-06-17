"""Dependency-light tests for the local-first benchmark support code."""

from __future__ import annotations

import math
import json
import tempfile
import unittest
import importlib.util
from argparse import Namespace
from pathlib import Path

from mpot.benchmarks.benchmark_plan import (
    create_benchmark_plan,
    input_sizes_from_n,
    process_counts_for_max,
    round_up_to_multiple,
)
from mpot.benchmarks.benchmark_budget import (
    benchmark_budget_markdown,
    build_benchmark_budget,
    write_benchmark_budget,
)
from mpot.benchmarks.benchmark_scenarios import (
    benchmark_scenarios_markdown,
    build_benchmark_scenarios,
    write_benchmark_scenarios,
)
from mpot.benchmarks.animation import animate_best_path
from mpot.benchmarks.artifacts import assignment_csv_rows, comm_event_csv_rows
from mpot.benchmarks.cli import apply_config_overrides, parse_int_list
from mpot.benchmarks.cluster import build_cluster_plan, cluster_plan_markdown, hostfile_text, parse_hosts, write_cluster_plan
from mpot.benchmarks.communication import analyze_communication, communication_markdown, write_communication_analysis
from mpot.benchmarks.config import (
    config_from_dict,
    config_hash,
    config_hash_from_dict,
    config_to_dict,
    load_config,
)
from mpot.benchmarks.correctness import compare_run_directories, compare_task_results
from mpot.benchmarks.defense_pack import build_defense_guide, defense_guide_markdown, write_defense_guide
from mpot.benchmarks.doctor import build_setup_doctor, setup_doctor_markdown, write_setup_doctor
from mpot.benchmarks.environment import build_environment_markdown, package_status, write_environment_artifacts
from mpot.benchmarks.experiment_index import build_experiment_index, experiment_index_markdown, write_experiment_index
from mpot.benchmarks.final_audit import build_final_audit, final_audit_markdown, write_final_audit
from mpot.benchmarks.granularity import analyze_granularity, granularity_markdown, write_granularity_analysis
from mpot.benchmarks.metrics import compute_efficiency, compute_speedup, summarize_load_balance
from mpot.benchmarks.mpi_scheduler import build_tasks, cyclic_chunks, cyclic_owner, validate_assignment
from mpot.benchmarks.ownership import build_ownership_report, ownership_markdown, write_ownership_report
from mpot.benchmarks.pipeline import build_pipeline_commands, select_final_value
from mpot.benchmarks.report_bundle import BundleError, create_report_bundle, slugify
from mpot.benchmarks.report_sync import build_report_sync, report_sync_markdown, write_report_sync
from mpot.benchmarks.reduction import RankTiming, TaskResult, choose_best
from mpot.benchmarks.results_summary import build_results_summary, results_summary_markdown, write_results_summary
from mpot.benchmarks.result_tables import build_speedup_rows, build_runtime_rows, export_result_tables
from mpot.benchmarks.run_reuse import expected_run_metadata
from mpot.benchmarks.solution_quality import (
    solution_quality_markdown,
    validate_solution_quality,
    write_solution_quality,
)
from mpot.benchmarks.submission_package import create_submission_package, submission_markdown
from mpot.benchmarks.validation import (
    ValidationItem,
    validate_benchmark_budget,
    validate_benchmark_plan,
    validate_communication_analysis,
    validate_defense_guide,
    validate_environment_report,
    validate_experiment_index,
    validate_granularity_analysis,
    validate_ownership_report,
    validate_report_bundle,
    validate_report_sync,
    validate_results_summary,
    validate_result_tables_manifest,
    validate_solution_quality_report,
    validate_submission_package_manifest,
    validation_summary,
)


class SchedulerTests(unittest.TestCase):
    def test_cyclic_owner(self):
        self.assertEqual(cyclic_owner(0, 4), 0)
        self.assertEqual(cyclic_owner(3, 4), 3)
        self.assertEqual(cyclic_owner(4, 4), 0)
        self.assertEqual(cyclic_owner(7, 4), 3)

    def test_cyclic_chunks_cover_every_task_once(self):
        tasks = build_tasks(total_tasks=10, base_seed=100)
        chunks = cyclic_chunks(tasks, size=4)
        validate_assignment(tasks, chunks)
        self.assertEqual([task.task_id for task in chunks[0]], [0, 4, 8])
        self.assertEqual([task.task_id for task in chunks[1]], [1, 5, 9])
        self.assertEqual([task.task_id for task in chunks[2]], [2, 6])
        self.assertEqual([task.task_id for task in chunks[3]], [3, 7])


class ArtifactRowTests(unittest.TestCase):
    def test_assignment_rows_make_cyclic_mapping_visible(self):
        rows = assignment_csv_rows(
            "mpi-unit",
            [
                {"rank": 0, "num_tasks": 2, "task_ids": [0, 2]},
                {"rank": 1, "num_tasks": 2, "task_ids": [1, 3]},
            ],
        )

        self.assertEqual([row["task_id"] for row in rows], [0, 1, 2, 3])
        self.assertEqual(rows[3]["rank"], 1)
        self.assertEqual(rows[3]["process_count"], 2)
        self.assertEqual(rows[3]["mapping_rule"], "task_id mod process_count")

    def test_comm_event_rows_keep_collective_trace_fields(self):
        rows = comm_event_csv_rows(
            "mpi-unit",
            [
                {
                    "event_index": 0,
                    "rank": 1,
                    "size": 2,
                    "hostname": "host",
                    "event": "scatter_tasks",
                    "collective": "scatter",
                    "root": 0,
                    "blocking": True,
                    "duration_s": 0.1,
                    "payload_count": 2,
                }
            ],
        )

        self.assertEqual(rows[0]["run_id"], "mpi-unit")
        self.assertEqual(rows[0]["collective"], "scatter")
        self.assertTrue(rows[0]["blocking"])
        self.assertEqual(rows[0]["payload_count"], 2)


class ReductionTests(unittest.TestCase):
    def _result(self, cost, task_id, seed):
        return TaskResult(
            task_id=task_id,
            seed=seed,
            rank=0,
            best_cost=cost,
            opt_iters=1,
            runtime_s=0.1,
            num_particles=2,
            traj_len=4,
            collision_fraction=0.0,
            trajectory=[[0.0, 0.0, 0.0, 0.0]],
        )

    def test_choose_best_uses_cost_then_task_then_seed(self):
        results = [
            self._result(1.0, 5, 1005),
            self._result(0.5, 9, 1009),
            self._result(0.5, 3, 1003),
        ]
        best = choose_best(results)
        self.assertEqual(best.task_id, 3)
        self.assertEqual(best.seed, 1003)


class CorrectnessTests(unittest.TestCase):
    def _result(self, task_id, seed, cost, rank=0):
        return TaskResult(
            task_id=task_id,
            seed=seed,
            rank=rank,
            best_cost=cost,
            opt_iters=2,
            runtime_s=0.1,
            num_particles=3,
            traj_len=5,
            collision_fraction=0.0,
            trajectory=[[0.0, 0.0, 0.0, 0.0]],
        )

    def test_task_level_comparison_passes_for_same_seed_and_cost(self):
        serial = [self._result(0, 100, 1.0), self._result(1, 101, 0.5)]
        mpi = [self._result(1, 101, 0.5, rank=1), self._result(0, 100, 1.0, rank=0)]
        rows, summary = compare_task_results(serial, mpi, tolerance=1.0e-9)

        self.assertTrue(summary["tasks_passed"])
        self.assertEqual(summary["num_compared_tasks"], 2)
        self.assertTrue(all(row.passed for row in rows))

    def test_task_level_comparison_fails_for_mismatch(self):
        serial = [self._result(0, 100, 1.0), self._result(1, 101, 0.5)]
        mpi = [self._result(0, 999, 1.1)]
        rows, summary = compare_task_results(serial, mpi, tolerance=1.0e-9)

        self.assertFalse(summary["tasks_passed"])
        self.assertFalse(summary["same_task_ids"])
        self.assertFalse(summary["all_seeds_match"])
        self.assertEqual(summary["missing_in_mpi"], [1])
        self.assertTrue(any(not row.passed for row in rows))

    def test_compare_run_directories_includes_task_level_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serial_dir = root / "serial"
            mpi_dir = root / "mpi"
            summary = {
                "run_id": "unit",
                "total_tasks": 1,
                "best_task_id": 0,
                "best_seed": 100,
                "best_cost": 1.0,
            }
            for run_dir in [serial_dir, mpi_dir]:
                run_dir.mkdir(parents=True)
                self._write_json(run_dir / "summary.json", summary)
                self._write_json(run_dir / "task_results.json", [self._result(0, 100, 1.0).to_json()])

            payload, rows = compare_run_directories(serial_dir, mpi_dir, tolerance=1.0e-9)
            self.assertTrue(payload["passed"])
            self.assertTrue(payload["task_level"]["tasks_passed"])
            self.assertEqual(len(rows), 1)

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)


class MetricTests(unittest.TestCase):
    def test_speedup_and_efficiency(self):
        self.assertAlmostEqual(compute_speedup(10.0, 2.5), 4.0)
        self.assertAlmostEqual(compute_efficiency(4.0, 8), 0.5)
        self.assertTrue(math.isnan(compute_speedup(0.0, 2.0)))

    def test_load_balance_threshold(self):
        timings = [
            RankTiming(0, 2, "a", 2, 8.0, 1.0, 9.0, 1.0),
            RankTiming(1, 2, "b", 2, 7.0, 1.0, 8.0, 1.2),
        ]
        summary = summarize_load_balance(timings)
        self.assertLess(summary.idle_fraction, 0.25)
        self.assertTrue(summary.balanced_under_25_percent)


class ConfigTests(unittest.TestCase):
    def test_minimal_config_loads_defaults(self):
        cfg = config_from_dict({"experiment_name": "unit", "total_tasks": 2})
        self.assertEqual(cfg.experiment_name, "unit")
        self.assertEqual(cfg.total_tasks, 2)
        self.assertEqual(cfg.seed_list(), [cfg.base_seed, cfg.base_seed + 1])

    def test_invalid_device_rejected(self):
        with self.assertRaises(ValueError):
            config_from_dict({"device": "cuda"})

    def test_invalid_iteration_window_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_outer_iters"):
            config_from_dict(
                {
                    "optimizer": {
                        "min_outer_iters": 4,
                        "max_outer_iters": 4,
                    }
                }
            )

    def test_cli_overrides(self):
        cfg = config_from_dict({"experiment_name": "unit", "total_tasks": 2})
        args = Namespace(
            experiment_name="override",
            output_dir="tmp_results",
            total_tasks=5,
            base_seed=99,
            traj_len=12,
            num_particles=3,
            num_probe=2,
            max_outer_iters=7,
            max_inner_iters=11,
        )
        cfg = apply_config_overrides(cfg, args)
        self.assertEqual(cfg.experiment_name, "override")
        self.assertEqual(cfg.output_dir, "tmp_results")
        self.assertEqual(cfg.total_tasks, 5)
        self.assertEqual(cfg.seed_list()[0], 99)
        self.assertEqual(cfg.problem.traj_len, 12)
        self.assertEqual(cfg.optimizer.num_particles, 3)
        self.assertEqual(cfg.optimizer.max_outer_iters, 7)

    def test_parse_int_list(self):
        self.assertEqual(parse_int_list("1, 2,4"), [1, 2, 4])
        with self.assertRaises(ValueError):
            parse_int_list("")

    def test_config_hash_is_stable_and_sensitive_to_config(self):
        cfg = config_from_dict({"experiment_name": "unit", "total_tasks": 2})
        same_payload = config_to_dict(cfg)
        self.assertEqual(config_hash(cfg), config_hash_from_dict(same_payload))

        changed = config_to_dict(cfg)
        changed["total_tasks"] = 3
        self.assertNotEqual(config_hash(cfg), config_hash_from_dict(changed))

    def test_2d_variant_configs_load(self):
        variants = {
            "configs/variant_open_2d.json": 1,
            "configs/variant_narrow_passage_2d.json": 4,
            "configs/variant_cluttered_2d.json": 6,
            "configs/variant_dense_sampling_2d.json": 10,
        }

        for path, expected_obstacles in variants.items():
            with self.subTest(path=path):
                cfg = load_config(path)
                self.assertEqual(cfg.device, "cpu")
                self.assertEqual(len(cfg.problem.start), 4)
                self.assertEqual(len(cfg.problem.goal), 4)
                self.assertEqual(len(cfg.problem.obstacles), expected_obstacles)
                self.assertGreaterEqual(cfg.total_tasks, expected_obstacles)


class ValidationTests(unittest.TestCase):
    def test_validation_summary(self):
        items = [
            ValidationItem("a", True, "ok"),
            ValidationItem("b", False, "missing"),
        ]
        payload = validation_summary(items)
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["num_items"], 2)
        self.assertEqual(payload["num_failed"], 1)


class OwnershipTests(unittest.TestCase):
    def test_default_ownership_report_is_balanced_and_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(__file__).resolve().parents[1]
            payload = build_ownership_report(repo_root=repo_root)

            self.assertTrue(payload["passed"], payload["members"])
            self.assertEqual(payload["num_members"], 4)
            self.assertLessEqual(
                max(member["meaningful_lines"] for member in payload["members"]),
                payload["recommended_max_lines_per_member"],
            )
            self.assertGreaterEqual(
                min(member["meaningful_lines"] for member in payload["members"]),
                payload["minimum_lines_per_member"],
            )
            self.assertIn("Team Code Ownership Report", ownership_markdown(payload))

            json_path, md_path = write_ownership_report(
                payload=payload,
                json_path=Path(tmp) / "ownership.json",
                markdown_path=Path(tmp) / "ownership.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_ownership_report(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class DefenseGuideTests(unittest.TestCase):
    def test_default_defense_guide_is_complete_and_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(__file__).resolve().parents[1]
            payload = build_defense_guide(repo_root=repo_root, max_symbols_per_file=6)

            self.assertTrue(payload["passed"], payload["missing_files"])
            self.assertEqual(payload["num_members"], 4)
            self.assertTrue(all(member["files"] for member in payload["members"]))
            self.assertTrue(all(member["demo_commands"] for member in payload["members"]))
            self.assertTrue(all(member["practice_questions"] for member in payload["members"]))
            self.assertIn("Member Defense Guide", defense_guide_markdown(payload))

            json_path, md_path = write_defense_guide(
                payload=payload,
                json_path=Path(tmp) / "defense.json",
                markdown_path=Path(tmp) / "defense.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_defense_guide(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class EnvironmentTests(unittest.TestCase):
    def test_package_status_detects_standard_library_module(self):
        status = package_status("json")
        self.assertTrue(status["installed"])

    def test_environment_markdown_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "label": "unit",
                "captured_at": "2026-06-17 00:00:00 +0700",
                "repo_root": str(root),
                "hostname": "host",
                "platform": {"system": "TestOS", "release": "1", "machine": "x86", "processor": ""},
                "python": {"executable": "python", "version": "3.11", "version_full": "3.11"},
                "cpu": {"logical_count": 4},
                "packages": [{"name": "json", "installed": True, "version": "installed", "error": ""}],
                "mpi": {"mpirun": {"executable": "mpirun", "output": "mpirun test"}, "mpi4py": {}},
                "git": {"branch": "main", "head": "abc", "dirty": False},
            }
            markdown = build_environment_markdown(payload)
            self.assertIn("Environment Report", markdown)
            json_path, markdown_path = write_environment_artifacts(
                payload=payload,
                json_path=root / "environment.json",
                markdown_path=root / "ENVIRONMENT.md",
            )

            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            items = validate_environment_report(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class SetupDoctorTests(unittest.TestCase):
    def test_setup_doctor_passes_for_standard_library_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = build_setup_doctor(
                repo_root=root,
                label="unit",
                packages=["json"],
                require_mpirun=False,
                run_probe=False,
            )

            self.assertTrue(payload["ready"], payload["items"])
            self.assertEqual(payload["num_failed"], 0)
            self.assertIn("Setup Doctor", setup_doctor_markdown(payload))
            json_path, md_path = write_setup_doctor(payload, root / "doctor.json", root / "doctor.md")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_setup_doctor_fails_for_impossible_python_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_setup_doctor(
                repo_root=tmp,
                label="unit",
                packages=["json"],
                min_python=(99, 0),
                require_mpirun=False,
                run_probe=False,
            )

            self.assertFalse(payload["ready"])
            self.assertTrue(any(item["name"] == "python version is supported" for item in payload["items"]))


class GranularityTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _write_rank_timings(self, path: Path):
        path.write_text(
            "run_id,rank,size,hostname,num_tasks,compute_time_s,communication_time_s,total_time_s,best_cost\n"
            "mpi-unit,0,2,host,2,8.0,1.0,9.0,1.0\n"
            "mpi-unit,1,2,host,2,7.8,1.0,8.8,1.2\n",
            encoding="utf-8",
        )

    def test_analyze_granularity_balanced_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "mpi-unit"
            run.mkdir(parents=True)
            self._write_json(run / "summary.json", {"run_id": "mpi-unit", "total_tasks": 4, "size": 2})
            self._write_rank_timings(run / "rank_timings.csv")

            payload = analyze_granularity(run)
            self.assertTrue(payload["balanced_under_threshold"])
            self.assertEqual(len(payload["rank_rows"]), 2)
            self.assertIn("acceptable", payload["recommendation"])
            self.assertIn("Granularity", granularity_markdown(payload))

    def test_write_and_validate_granularity_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "run_id": "mpi-unit",
                "input_size_n": 4,
                "processes": 2,
                "threshold": 0.25,
                "idle_fraction": 0.1,
                "balanced_under_threshold": True,
                "communication_fraction_of_slowest_rank": 0.05,
                "recommendation": "ok",
                "rank_rows": [
                    {
                        "rank": 0,
                        "num_tasks": 2,
                        "compute_time_s": 1.0,
                        "communication_time_s": 0.1,
                        "total_time_s": 1.1,
                        "idle_time_s": 0.0,
                        "idle_fraction_of_slowest_rank": 0.0,
                    }
                ],
            }
            json_path, md_path = write_granularity_analysis(
                payload=payload,
                json_path=root / "granularity.json",
                markdown_path=root / "granularity.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_granularity_analysis(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class CommunicationTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _write_comm_events(self, path: Path):
        path.write_text(
            "run_id,rank,size,hostname,event_index,event,collective,root,blocking,duration_s,payload_count\n"
            "mpi-unit,0,2,host,0,bcast_config,bcast,0,True,0.1,\n"
            "mpi-unit,1,2,host,0,bcast_config,bcast,0,True,0.2,\n"
            "mpi-unit,0,2,host,1,scatter_tasks,scatter,0,True,0.3,2\n"
            "mpi-unit,1,2,host,1,scatter_tasks,scatter,0,True,0.4,2\n"
            "mpi-unit,0,2,host,2,gather_results,gather,0,True,0.5,1\n"
            "mpi-unit,1,2,host,2,gather_results,gather,0,True,0.6,1\n",
            encoding="utf-8",
        )

    def test_analyze_and_validate_communication(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "mpi-unit"
            run.mkdir(parents=True)
            self._write_json(run / "summary.json", {"run_id": "mpi-unit", "total_tasks": 4, "size": 2})
            self._write_comm_events(run / "comm_events.csv")

            payload = analyze_communication(run)
            self.assertTrue(payload["all_events_blocking"])
            self.assertTrue(payload["has_expected_collectives"])
            self.assertEqual(len(payload["event_rows"]), 3)
            self.assertIn("Communication Strategy", communication_markdown(payload))

            json_path, md_path = write_communication_analysis(
                payload=payload,
                json_path=Path(tmp) / "communication.json",
                markdown_path=Path(tmp) / "communication.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_communication_analysis(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class SolutionQualityTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_validate_solution_quality_passes_for_valid_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "mpi-unit"
            trajectory = [
                [-1.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [1.0, 1.0, 0.0, 0.0],
            ]
            self._write_json(
                run / "summary.json",
                {
                    "run_id": "mpi-unit",
                    "mode": "mpi",
                    "size": 2,
                    "total_tasks": 1,
                    "best_task_id": 0,
                    "best_seed": 100,
                    "best_collision_fraction": 0.0,
                    "problem": {
                        "start": [-1.0, -1.0, 0.0, 0.0],
                        "goal": [1.0, 1.0, 0.0, 0.0],
                        "traj_len": 3,
                        "workspace_min": [-1.0, -1.0],
                        "workspace_max": [1.0, 1.0],
                        "obstacles": [{"center": [0.75, -0.75], "radius": 0.1}],
                    },
                },
            )
            self._write_json(
                run / "task_results.json",
                [
                    {
                        "task_id": 0,
                        "seed": 100,
                        "rank": 0,
                        "best_cost": 1.0,
                        "collision_fraction": 0.0,
                        "trajectory": trajectory,
                    }
                ],
            )

            payload = validate_solution_quality(run)
            self.assertTrue(payload["passed"], payload["checks"])
            self.assertIn("Solution Quality", solution_quality_markdown(payload))
            json_path, md_path = write_solution_quality(
                payload=payload,
                json_path=Path(tmp) / "quality.json",
                markdown_path=Path(tmp) / "quality.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_solution_quality_report(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class ExperimentIndexTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_build_and_validate_experiment_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            report = root / "report"
            self._write_json(
                results / "serial-unit-N2" / "summary.json",
                {
                    "run_id": "serial-unit-N2",
                    "mode": "serial",
                    "total_tasks": 2,
                    "size": 1,
                    "best_cost": 0.1,
                    "runtime_with_communication_s": 2.0,
                    "runtime_without_communication_s": 2.0,
                    "config": {"experiment_name": "unit_N2"},
                },
            )
            self._write_json(
                results / "mpi-unit-N2-P2" / "summary.json",
                {
                    "run_id": "mpi-unit-N2-P2",
                    "mode": "mpi",
                    "total_tasks": 2,
                    "size": 2,
                    "best_cost": 0.1,
                    "runtime_with_communication_s": 1.2,
                    "runtime_without_communication_s": 1.1,
                    "config": {"experiment_name": "unit_N2"},
                },
            )
            (results / "mpi-unit-N2-P2" / "rank_timings.csv").write_text("rank\n0\n", encoding="utf-8")
            (results / "mpi-unit-N2-P2" / "comm_events.csv").write_text("event\nbcast_config\n", encoding="utf-8")
            (results / "mpi-unit-N2-P2" / "task_assignment.csv").write_text("run_id,rank,task_id\nunit,0,0\n", encoding="utf-8")
            self._write_json(results / "compare-unit" / "correctness_report.json", {"run_id": "compare-unit", "passed": True})
            self._write_json(results / "communication-unit-N2-P2.json", {"run_id": "mpi-unit-N2-P2", "passed": True})
            self._write_json(results / "solution-quality-unit-N2-P2.json", {"run_id": "mpi-unit-N2-P2", "passed": True})
            self._write_json(report / "TEAM_OWNERSHIP_REPORT.json", {"run_id": "team-ownership", "passed": True})
            self._write_json(report / "MEMBER_DEFENSE_GUIDE.json", {"run_id": "member-defense", "passed": True})
            self._write_json(report / "tables" / "tables_manifest_unit.json", {"label": "unit"})

            payload = build_experiment_index(results_dir=results, report_dir=report, label="unit")
            self.assertEqual(payload["counts"]["runs"], 2)
            self.assertEqual(payload["counts"]["mpi_runs"], 1)
            self.assertEqual(payload["counts"]["communication_reports"], 1)
            self.assertEqual(payload["counts"]["solution_quality_reports"], 1)
            self.assertEqual(payload["counts"]["ownership_reports"], 1)
            self.assertEqual(payload["counts"]["defense_guides"], 1)
            markdown = experiment_index_markdown(payload)
            self.assertIn("Experiment Index", markdown)
            self.assertIn("Communication Reports", markdown)
            self.assertIn("Solution Quality Reports", markdown)
            self.assertIn("Team Ownership Reports", markdown)
            self.assertIn("Member Defense Guides", markdown)

            json_path, md_path = write_experiment_index(payload, report / "index.json", report / "index.md")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_experiment_index(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class FinalAuditTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _touch(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact\n", encoding="utf-8")

    def _write_summary(self, results: Path, run_id: str, mode: str, n: int, processes: int):
        self._write_json(
            results / run_id / "summary.json",
            {
                "run_id": run_id,
                "mode": mode,
                "total_tasks": n,
                "size": processes,
                "best_cost": 0.5,
                "runtime_with_communication_s": 1.0,
                "runtime_without_communication_s": 0.9,
                "config": {"experiment_name": "unit_N2"},
            },
        )

    def test_final_audit_passes_for_complete_artifact_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            report = root / "report"

            for n in [2, 4]:
                self._write_summary(results, f"serial-unit-N{n}", "serial", n, 1)
                self._write_summary(results, f"mpi-unit-N{n}-P1", "mpi", n, 1)
                self._write_summary(results, f"mpi-unit-N{n}-P2", "mpi", n, 2)

            self._write_json(
                results / "compare-unit-N4-P2" / "correctness_report.json",
                {"passed": True, "task_level": {"tasks_passed": True}},
            )
            self._write_json(
                results / "granularity-unit-N2-P2.json",
                {"balanced_under_threshold": True, "idle_fraction": 0.05, "threshold": 0.25},
            )
            self._write_json(
                results / "communication-unit-N4-P2.json",
                {
                    "has_expected_collectives": True,
                    "all_events_blocking": True,
                    "observed_collectives": ["bcast", "gather", "scatter"],
                },
            )
            self._write_json(
                results / "solution-quality-unit-N4-P2.json",
                {
                    "passed": True,
                    "num_failed": 0,
                    "goal_error": 0.0,
                    "hard_collision_fraction": 0.0,
                },
            )
            self._write_json(results / "validation-unit-N4-P2.json", {"passed": True, "num_failed": 0})
            self._touch(results / "mpi-unit-N4-P2" / "comm_events.csv")
            self._touch(results / "mpi-unit-N4-P2" / "task_assignment.csv")
            self._write_json(results / "environment-unit.json", {"label": "unit"})
            self._write_json(
                report / "TEAM_OWNERSHIP_REPORT.json",
                {
                    "passed": True,
                    "num_members": 4,
                    "minimum_lines_per_member": 250,
                    "recommended_max_lines_per_member": 700,
                    "members": [
                        {"member": "Member A", "meaningful_lines": 400, "passed": True},
                        {"member": "Member B", "meaningful_lines": 420, "passed": True},
                        {"member": "Member C", "meaningful_lines": 430, "passed": True},
                        {"member": "Member D", "meaningful_lines": 440, "passed": True},
                    ],
                },
            )
            self._write_json(
                report / "MEMBER_DEFENSE_GUIDE.json",
                {
                    "passed": True,
                    "num_members": 4,
                    "members": [
                        {"member": "Member A", "files": [1], "demo_commands": ["a"], "practice_questions": ["q"]},
                        {"member": "Member B", "files": [1], "demo_commands": ["b"], "practice_questions": ["q"]},
                        {"member": "Member C", "files": [1], "demo_commands": ["c"], "practice_questions": ["q"]},
                        {"member": "Member D", "files": [1], "demo_commands": ["d"], "practice_questions": ["q"]},
                    ],
                },
            )
            self._write_json(report / "EXPERIMENT_INDEX_unit.json", {"label": "unit"})
            self._write_json(report / "artifacts" / "unit" / "manifest.json", {"entries": [1]})
            self._write_json(
                report / "tables" / "tables_manifest_unit.json",
                {"num_runtime_rows": 4, "num_speedup_rows": 2, "num_load_balance_rows": 2},
            )
            self._write_json(report / "RESULTS_SUMMARY_unit.json", {"passed": True})
            self._touch(report / "figures" / "runtime_vs_input_size_unit.png")
            self._touch(report / "figures" / "speedup_unit.png")
            self._touch(report / "figures" / "unit_mpi_mpi-unit-N2-P2_rank_time_breakdown.png")

            payload = build_final_audit(
                results_dir=results,
                report_dir=report,
                label="unit",
                input_sizes=[2, 4],
                process_counts=[1, 2],
                n=2,
                speedup_n=4,
                final_processes=2,
            )

            self.assertTrue(payload["final_ready"], payload["items"])
            self.assertEqual(payload["num_failed"], 0)
            self.assertIn("Final Experiment Audit", final_audit_markdown(payload))
            json_path, md_path = write_final_audit(payload, report / "audit.json", report / "audit.md")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_final_audit_fails_when_solution_quality_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            report = root / "report"

            for n in [2, 4]:
                self._write_summary(results, f"serial-unit-N{n}", "serial", n, 1)
                self._write_summary(results, f"mpi-unit-N{n}-P1", "mpi", n, 1)
                self._write_summary(results, f"mpi-unit-N{n}-P2", "mpi", n, 2)

            self._write_json(
                results / "compare-unit-N4-P2" / "correctness_report.json",
                {"passed": True, "task_level": {"tasks_passed": True}},
            )
            self._write_json(
                results / "granularity-unit-N2-P2.json",
                {"balanced_under_threshold": True, "idle_fraction": 0.05, "threshold": 0.25},
            )
            self._write_json(
                results / "communication-unit-N4-P2.json",
                {
                    "has_expected_collectives": True,
                    "all_events_blocking": True,
                    "observed_collectives": ["bcast", "gather", "scatter"],
                },
            )
            self._write_json(
                results / "solution-quality-unit-N4-P2.json",
                {
                    "passed": False,
                    "num_failed": 1,
                    "goal_error": 0.2,
                    "hard_collision_fraction": 0.0,
                },
            )
            self._write_json(results / "validation-unit-N4-P2.json", {"passed": True, "num_failed": 0})
            self._touch(results / "mpi-unit-N4-P2" / "comm_events.csv")
            self._touch(results / "mpi-unit-N4-P2" / "task_assignment.csv")
            self._write_json(results / "environment-unit.json", {"label": "unit"})
            self._write_json(
                report / "TEAM_OWNERSHIP_REPORT.json",
                {
                    "passed": True,
                    "num_members": 4,
                    "minimum_lines_per_member": 250,
                    "recommended_max_lines_per_member": 700,
                    "members": [
                        {"member": "Member A", "meaningful_lines": 400, "passed": True},
                        {"member": "Member B", "meaningful_lines": 420, "passed": True},
                        {"member": "Member C", "meaningful_lines": 430, "passed": True},
                        {"member": "Member D", "meaningful_lines": 440, "passed": True},
                    ],
                },
            )
            self._write_json(
                report / "MEMBER_DEFENSE_GUIDE.json",
                {
                    "passed": True,
                    "num_members": 4,
                    "members": [
                        {"member": "Member A", "files": [1], "demo_commands": ["a"], "practice_questions": ["q"]},
                        {"member": "Member B", "files": [1], "demo_commands": ["b"], "practice_questions": ["q"]},
                        {"member": "Member C", "files": [1], "demo_commands": ["c"], "practice_questions": ["q"]},
                        {"member": "Member D", "files": [1], "demo_commands": ["d"], "practice_questions": ["q"]},
                    ],
                },
            )
            self._write_json(report / "EXPERIMENT_INDEX_unit.json", {"label": "unit"})
            self._write_json(report / "artifacts" / "unit" / "manifest.json", {"entries": [1]})
            self._write_json(
                report / "tables" / "tables_manifest_unit.json",
                {"num_runtime_rows": 4, "num_speedup_rows": 2, "num_load_balance_rows": 2},
            )
            self._write_json(report / "RESULTS_SUMMARY_unit.json", {"passed": True})
            self._touch(report / "figures" / "runtime_vs_input_size_unit.png")
            self._touch(report / "figures" / "speedup_unit.png")
            self._touch(report / "figures" / "unit_mpi_mpi-unit-N2-P2_rank_time_breakdown.png")

            payload = build_final_audit(
                results_dir=results,
                report_dir=report,
                label="unit",
                input_sizes=[2, 4],
                process_counts=[1, 2],
                n=2,
                speedup_n=4,
                final_processes=2,
            )

            self.assertFalse(payload["final_ready"])
            failed_names = [item["name"] for item in payload["items"] if not item["passed"]]
            self.assertIn("solution quality passed", failed_names)

    def test_final_audit_fails_when_speedup_baseline_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            report = root / "report"
            self._write_summary(results, "serial-unit-N4", "serial", 4, 1)
            self._write_summary(results, "mpi-unit-N4-P2", "mpi", 4, 2)

            payload = build_final_audit(
                results_dir=results,
                report_dir=report,
                label="unit",
                input_sizes=[4],
                process_counts=[1, 2],
                n=4,
                speedup_n=4,
                final_processes=2,
            )

            self.assertFalse(payload["final_ready"])
            self.assertTrue(any("P=1" in item["name"] for item in payload["items"] if not item["passed"]))


class ReportBundleTests(unittest.TestCase):
    def _write_text(self, path: Path, text: str = "artifact\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _make_run(self, root: Path, name: str, mode: str):
        run = root / name
        summary = {
            "run_id": name,
            "mode": mode,
            "total_tasks": 4,
            "size": 1 if mode == "serial" else 2,
            "runtime_with_communication_s": 1.0,
            "runtime_without_communication_s": 0.9,
        }
        self._write_json(run / "summary.json", summary)
        self._write_json(run / "config.json", {"experiment_name": "unit"})
        self._write_json(run / "task_results.json", [])
        self._write_text(run / "task_results.csv", "run_id,task_id\nunit,0\n")
        self._write_text(run / "best_trajectory.npy", "fake-npy")
        self._write_text(run / "best_path.png", "fake-png")
        self._write_text(run / "cost_by_task.png", "fake-png")
        if mode == "mpi":
            self._write_text(run / "rank_timings.csv", "rank,total_time_s\n0,1.0\n")
            self._write_text(run / "comm_events.csv", "run_id,rank,event,duration_s\nunit,0,bcast_config,0.1\n")
            self._write_text(run / "task_assignment.csv", "run_id,rank,local_index,task_id,mapping_rule\nunit,0,0,0,task_id mod process_count\n")
            self._write_text(run / "rank_time_breakdown.png", "fake-png")
        return run

    def test_slugify(self):
        self.assertEqual(slugify("smoke local / np=4"), "smoke-local-np-4")
        self.assertEqual(slugify(""), "artifact")

    def test_create_report_bundle_copies_real_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serial = self._make_run(root, "serial-unit", "serial")
            mpi = self._make_run(root, "mpi-unit", "mpi")
            correctness = root / "compare" / "correctness_report.json"
            validation = root / "validation_report.json"
            self._write_json(correctness, {"passed": True})
            self._write_json(validation, {"passed": True})

            manifest = create_report_bundle(
                report_dir=root / "report",
                bundle_name="unit-bundle",
                serial_runs=[serial],
                mpi_runs=[mpi],
                correctness_reports=[correctness],
                validation_reports=[validation],
                generate_plots=False,
            )

            self.assertEqual(manifest["bundle_name"], "unit-bundle")
            self.assertTrue((root / "report" / "artifacts" / "unit-bundle" / "manifest.json").exists())
            self.assertTrue((root / "report" / "ARTIFACT_MANIFEST.md").exists())
            self.assertGreaterEqual(len(manifest["entries"]), 15)
            self.assertTrue(all(entry["exists"] for entry in manifest["entries"]))
            items = validate_report_bundle(manifest["manifest_path"])
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])

    def test_create_report_bundle_fails_when_required_artifact_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serial = self._make_run(root, "serial-unit", "serial")
            (serial / "summary.json").unlink()
            with self.assertRaises(BundleError):
                create_report_bundle(
                    report_dir=root / "report",
                    bundle_name="broken",
                    serial_runs=[serial],
                    generate_plots=False,
                )

    def test_dry_run_does_not_write_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serial = self._make_run(root, "serial-unit", "serial")
            manifest = create_report_bundle(
                report_dir=root / "report",
                bundle_name="dry",
                serial_runs=[serial],
                generate_plots=True,
                dry_run=True,
            )

            self.assertTrue(manifest["dry_run"])
            self.assertFalse((root / "report" / "artifacts" / "dry" / "manifest.json").exists())
            self.assertFalse((root / "report" / "figures" / "runtime_vs_input_size.png").exists())

    def test_clean_existing_removes_stale_bundle_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serial = self._make_run(root, "serial-unit", "serial")
            stale = root / "report" / "artifacts" / "clean" / "stale.txt"
            stale.parent.mkdir(parents=True)
            stale.write_text("old\n", encoding="utf-8")

            create_report_bundle(
                report_dir=root / "report",
                bundle_name="clean",
                serial_runs=[serial],
                generate_plots=False,
                clean_existing=True,
            )

            self.assertFalse(stale.exists())
            self.assertTrue((root / "report" / "artifacts" / "clean" / "manifest.json").exists())


class ResultTableTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _write_rank_timings(self, run_dir: Path, run_id: str, size: int):
        rows = [
            "run_id,rank,size,hostname,num_tasks,compute_time_s,communication_time_s,total_time_s,best_cost\n",
        ]
        for rank in range(size):
            total = 10.0 / size + rank * 0.1
            rows.append(f"{run_id},{rank},{size},host,{2}, {total - 0.2},0.2,{total},1.0\n")
        (run_dir / "rank_timings.csv").write_text("".join(rows), encoding="utf-8")

    def _make_summary(self, root: Path, run_id: str, mode: str, size: int, n: int, runtime: float):
        run = root / run_id
        run.mkdir(parents=True, exist_ok=True)
        self._write_json(
            run / "summary.json",
            {
                "run_id": run_id,
                "mode": mode,
                "size": size,
                "total_tasks": n,
                "runtime_with_communication_s": runtime,
                "runtime_without_communication_s": runtime - 0.2,
                "best_cost": 0.5,
                "load_balance": {"balanced_under_25_percent": True},
                "config": {"experiment_name": "unit_sweep"},
            },
        )
        if mode == "mpi":
            self._write_rank_timings(run, run_id, size)
        return run

    def test_runtime_and_speedup_rows_use_real_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_summary(root, "mpi-unit-N4-P1", "mpi", 1, 4, 8.0)
            self._make_summary(root, "mpi-unit-N4-P2", "mpi", 2, 4, 5.0)
            self._make_summary(root, "serial-unit-N4", "serial", 1, 4, 9.0)

            runtime_rows = build_runtime_rows(root, label="unit")
            speedup_rows = build_speedup_rows(root, label="unit", input_size=4)

            self.assertEqual(len(runtime_rows), 3)
            self.assertEqual([row["processes"] for row in speedup_rows], [1, 2])
            self.assertAlmostEqual(speedup_rows[1]["speedup_with_communication"], 8.0 / 5.0)

    def test_export_result_tables_writes_csv_markdown_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_summary(root / "results", "mpi-unit-N4-P1", "mpi", 1, 4, 8.0)
            self._make_summary(root / "results", "mpi-unit-N4-P2", "mpi", 2, 4, 5.0)
            out = root / "tables"

            paths = export_result_tables(
                results_dir=root / "results",
                output_dir=out,
                label="unit",
                input_size=4,
            )

            self.assertTrue(paths.runtime_csv.exists())
            self.assertTrue(paths.speedup_csv.exists())
            self.assertTrue(paths.load_balance_csv and paths.load_balance_csv.exists())
            self.assertTrue(paths.markdown.exists())
            self.assertIn("Generated Results Tables", paths.markdown.read_text(encoding="utf-8"))
            manifest = json.loads(paths.manifest_json.read_text(encoding="utf-8"))
            self.assertEqual(manifest["num_speedup_rows"], 2)
            items = validate_result_tables_manifest(paths.manifest_json)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class ResultsSummaryTests(unittest.TestCase):
    def _write(self, path: Path, text: str = "ok\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_build_write_and_validate_results_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serial = root / "results" / "serial-unit-N4"
            mpi = root / "results" / "mpi-unit-N4-P2"
            self._write_json(
                serial / "summary.json",
                {
                    "run_id": "serial-unit-N4",
                    "mode": "serial",
                    "total_tasks": 4,
                    "size": 1,
                    "best_task_id": 1,
                    "best_seed": 101,
                    "best_cost": 0.2,
                    "runtime_with_communication_s": 9.0,
                },
            )
            self._write_json(
                mpi / "summary.json",
                {
                    "run_id": "mpi-unit-N4-P2",
                    "mode": "mpi",
                    "total_tasks": 4,
                    "size": 2,
                    "best_task_id": 1,
                    "best_seed": 101,
                    "best_cost": 0.2,
                    "runtime_with_communication_s": 5.0,
                    "runtime_without_communication_s": 4.8,
                },
            )
            correctness = root / "results" / "compare" / "correctness_report.json"
            self._write_json(
                correctness,
                {
                    "passed": True,
                    "same_best_task": True,
                    "same_best_seed": True,
                    "best_cost_difference": 0.0,
                    "task_level": {"tasks_passed": True, "num_compared_tasks": 4},
                },
            )
            tables_dir = root / "report" / "tables"
            runtime_csv = tables_dir / "runtime_table_unit.csv"
            speedup_csv = tables_dir / "speedup_table_unit.csv"
            load_csv = tables_dir / "load_balance_table_unit.csv"
            self._write(runtime_csv, "run_id\nmpi-unit-N4-P2\n")
            self._write(speedup_csv, "run_id\nmpi-unit-N4-P2\n")
            self._write(load_csv, "rank\n0\n1\n")
            manifest = tables_dir / "tables_manifest_unit.json"
            self._write_json(
                manifest,
                {
                    "num_runtime_rows": 1,
                    "num_speedup_rows": 1,
                    "num_load_balance_rows": 2,
                    "paths": {
                        "runtime_csv": str(runtime_csv),
                        "speedup_csv": str(speedup_csv),
                        "load_balance_csv": str(load_csv),
                    },
                },
            )
            granularity = root / "results" / "granularity-unit-N4-P2.json"
            self._write_json(
                granularity,
                {
                    "balanced_under_threshold": True,
                    "idle_fraction": 0.1,
                    "communication_fraction_of_slowest_rank": 0.05,
                    "recommendation": "ok",
                },
            )
            communication = root / "results" / "communication-unit-N4-P2.json"
            self._write_json(
                communication,
                {
                    "has_expected_collectives": True,
                    "all_events_blocking": True,
                    "observed_collectives": ["bcast", "scatter", "gather"],
                    "topology": "star",
                    "communication_strategy": "blocking collectives",
                    "num_event_rows": 6,
                },
            )
            solution = root / "results" / "solution-quality-unit-N4-P2.json"
            self._write_json(
                solution,
                {
                    "passed": True,
                    "goal_error": 0.0,
                    "hard_collision_fraction": 0.0,
                    "max_bounds_violation": 0.0,
                },
            )
            figure = root / "report" / "figures" / "runtime_vs_input_size_unit.png"
            self._write(figure, "png")

            payload = build_results_summary(
                label="unit",
                serial_run=serial,
                mpi_run=mpi,
                correctness_report=correctness,
                tables_manifest=manifest,
                granularity_report=granularity,
                communication_report=communication,
                solution_quality_report=solution,
                figure_paths=[figure],
            )

            self.assertTrue(payload["passed"], payload["checks"])
            self.assertIn("Results Summary", results_summary_markdown(payload))
            json_path, md_path = write_results_summary(
                payload,
                root / "report" / "RESULTS_SUMMARY_unit.json",
                root / "report" / "RESULTS_SUMMARY_unit.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            items = validate_results_summary(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class PlotAnimationTests(unittest.TestCase):
    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_animate_best_path_writes_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            problem = {
                "workspace_min": [-1.0, -1.0],
                "workspace_max": [1.0, 1.0],
                "start": [-0.8, -0.8, 0.0, 0.0],
                "goal": [0.8, 0.8, 0.0, 0.0],
                "obstacles": [{"center": [0.0, 0.0], "radius": 0.1, "safety_margin": 0.05}],
            }
            trajectory = [
                [-0.8, -0.8, 0.0, 0.0],
                [-0.2, -0.1, 0.0, 0.0],
                [0.3, 0.2, 0.0, 0.0],
                [0.8, 0.8, 0.0, 0.0],
            ]
            self._write_json(run_dir / "summary.json", {"best_task_id": 0, "problem": problem})
            self._write_json(run_dir / "task_results.json", [{"task_id": 0, "trajectory": trajectory}])

            out = animate_best_path(run_dir, output=run_dir / "trajectory.gif", fps=4)

            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


class ReportSyncTests(unittest.TestCase):
    def test_report_sync_passes_for_existing_paths_and_ignores_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "run_serial.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "report").mkdir()
            doc = root / "report" / "REPORT_DRAFT.md"
            doc.write_text(
                "`scripts/run_serial.py`\n"
                "`results/<run_id>/summary.json`\n",
                encoding="utf-8",
            )

            payload = build_report_sync(repo_root=root, documents=["report/REPORT_DRAFT.md"], label="unit")

            self.assertTrue(payload["passed"])
            self.assertEqual(payload["num_missing"], 0)
            self.assertIn("Report Sync Check", report_sync_markdown(payload))

    def test_report_sync_reports_missing_concrete_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            doc = root / "docs" / "plan.md"
            doc.write_text("Missing path: `scripts/missing.py`\n", encoding="utf-8")

            payload = build_report_sync(repo_root=root, documents=["docs/plan.md"], label="unit")

            self.assertFalse(payload["passed"])
            self.assertEqual(payload["num_missing"], 1)
            self.assertEqual(payload["missing"][0]["path"], "scripts/missing.py")

    def test_write_report_sync_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements-local.txt").write_text("numpy\n", encoding="utf-8")
            (root / "docs").mkdir()
            doc = root / "docs" / "plan.md"
            doc.write_text("See `requirements-local.txt`.\n", encoding="utf-8")
            payload = build_report_sync(repo_root=root, documents=["docs/plan.md"], label="unit")
            json_path, markdown_path = write_report_sync(
                payload=payload,
                json_path=root / "report" / "REPORT_SYNC_unit.json",
                markdown_path=root / "report" / "REPORT_SYNC_unit.md",
            )

            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            items = validate_report_sync(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class SubmissionPackageTests(unittest.TestCase):
    def _write(self, path: Path, text: str = "ok\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _make_required_artifacts(self, root: Path, label: str = "unit"):
        report = root / "report"
        docs = root / "docs"
        for path in [
            report / "REPORT_DRAFT.md",
            report / "REPORT_CHECKLIST.md",
            docs / "team_ownership.md",
            docs / "mpi_mpot_project_plan.md",
            report / f"FINAL_AUDIT_{label}.md",
            report / f"EXPERIMENT_INDEX_{label}.md",
            report / "TEAM_OWNERSHIP_REPORT.md",
            report / "MEMBER_DEFENSE_GUIDE.md",
            report / f"ENVIRONMENT_{label}.md",
            report / f"COMMUNICATION_{label}.md",
            report / f"GRANULARITY_{label}.md",
            report / f"SOLUTION_QUALITY_{label}.md",
            report / f"REPORT_SYNC_{label}.md",
            report / f"RESULTS_SUMMARY_{label}.md",
            report / "tables" / f"RESULTS_TABLES_{label}.md",
            report / "tables" / f"runtime_table_{label}.csv",
            report / "figures" / f"runtime_vs_input_size_{label}.png",
            report / "figures" / f"trajectory_{label}.gif",
        ]:
            self._write(path)

        self._write_json(report / f"FINAL_AUDIT_{label}.json", {"final_ready": True})
        self._write_json(report / f"EXPERIMENT_INDEX_{label}.json", {"counts": {"runs": 1}})
        self._write_json(report / "TEAM_OWNERSHIP_REPORT.json", {"passed": True, "members": []})
        self._write_json(report / "MEMBER_DEFENSE_GUIDE.json", {"passed": True, "members": []})
        self._write_json(report / f"REPORT_SYNC_{label}.json", {"passed": True, "num_missing": 0, "num_checked": 1})
        self._write_json(report / f"RESULTS_SUMMARY_{label}.json", {"passed": True, "checks": []})
        return report, docs

    def test_create_submission_package_copies_required_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report, docs = self._make_required_artifacts(root)
            payload = create_submission_package(
                label="unit",
                report_dir=report,
                docs_dir=docs,
                output_dir=root / "submission",
                clean=True,
            )

            self.assertTrue(payload["passed"])
            self.assertEqual(payload["num_missing_required"], 0)
            self.assertTrue((root / "submission" / "unit" / "SUBMISSION_MANIFEST.json").exists())
            self.assertTrue((root / "submission" / "unit" / "figures" / "trajectory_unit.gif").exists())
            self.assertIn("Submission Package Manifest", submission_markdown(payload))
            items = validate_submission_package_manifest(payload["manifest_json"])
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])

    def test_missing_required_submission_file_fails_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report, docs = self._make_required_artifacts(root)
            (report / "REPORT_CHECKLIST.md").unlink()
            payload = create_submission_package(
                label="unit",
                report_dir=report,
                docs_dir=docs,
                output_dir=root / "submission",
            )

            self.assertFalse(payload["passed"])
            self.assertGreater(payload["num_missing_required"], 0)
            missing_roles = [entry["role"] for entry in payload["entries"] if entry["required"] and not entry["exists"]]
            self.assertIn("report checklist", missing_roles)


class SweepScriptTests(unittest.TestCase):
    def _load_run_sweep(self):
        repo_root = Path(__file__).resolve().parents[1]
        path = repo_root / "scripts" / "run_sweep.py"
        spec = importlib.util.spec_from_file_location("run_sweep_script", path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module

    def test_run_is_complete_checks_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._load_run_sweep()
            root = Path(tmp)
            self.assertFalse(module.run_is_complete(root, "serial-unit-N2"))
            (root / "serial-unit-N2").mkdir(parents=True)
            self.assertFalse(module.run_is_complete(root, "serial-unit-N2"))
            (root / "serial-unit-N2" / "summary.json").write_text("{}", encoding="utf-8")
            self.assertTrue(module.run_is_complete(root, "serial-unit-N2"))

    def test_run_is_complete_checks_expected_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._load_run_sweep()
            root = Path(tmp)
            run = root / "mpi-unit-N2-P2"
            run.mkdir(parents=True)
            payload = {
                "run_id": "mpi-unit-N2-P2",
                "mode": "mpi",
                "total_tasks": 2,
                "size": 2,
                "experiment_name": "unit_N2",
                "config_hash": "abc",
            }
            (run / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

            self.assertTrue(
                module.run_is_complete(
                    root,
                    "mpi-unit-N2-P2",
                    expected={
                        "run_id": "mpi-unit-N2-P2",
                        "mode": "mpi",
                        "total_tasks": 2,
                        "size": 2,
                        "experiment_name": "unit_N2",
                        "config_hash": "abc",
                    },
                )
            )
            self.assertFalse(
                module.run_is_complete(
                    root,
                    "mpi-unit-N2-P2",
                    expected={
                        "run_id": "mpi-unit-N2-P2",
                        "mode": "mpi",
                        "total_tasks": 4,
                        "size": 2,
                        "experiment_name": "unit_N2",
                        "config_hash": "abc",
                    },
                )
            )

    def test_run_is_complete_rejects_missing_config_hash_when_expected(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._load_run_sweep()
            root = Path(tmp)
            run = root / "mpi-unit-N2-P2"
            run.mkdir(parents=True)
            payload = {
                "run_id": "mpi-unit-N2-P2",
                "mode": "mpi",
                "total_tasks": 2,
                "size": 2,
                "experiment_name": "unit_N2",
            }
            (run / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

            self.assertFalse(
                module.run_is_complete(
                    root,
                    "mpi-unit-N2-P2",
                    expected={
                        "run_id": "mpi-unit-N2-P2",
                        "mode": "mpi",
                        "total_tasks": 2,
                        "size": 2,
                        "experiment_name": "unit_N2",
                        "config_hash": "abc",
                    },
                )
            )

    def test_run_command_skips_existing_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = self._load_run_sweep()
            root = Path(tmp)
            run = root / "mpi-unit-N2-P2"
            run.mkdir(parents=True)
            (run / "summary.json").write_text("{}", encoding="utf-8")

            status = module.run_command(
                ["python", "-c", "raise SystemExit(99)"],
                dry_run=False,
                output_dir=root,
                run_id="mpi-unit-N2-P2",
                skip_existing=True,
            )

            self.assertEqual(status, "skipped")

    def test_mpi_prefix_supports_hostfile_options(self):
        module = self._load_run_sweep()
        command = module.mpi_prefix(
            processes=8,
            hostfile="configs/hostfile_ubuntu.txt",
            map_by="slot",
            bind_to="none",
            mca=[["btl_tcp_if_include", "enp0s1"]],
        )

        self.assertEqual(
            command,
            [
                "mpirun",
                "--hostfile",
                "configs/hostfile_ubuntu.txt",
                "-np",
                "8",
                "--map-by",
                "slot",
                "--bind-to",
                "none",
                "--mca",
                "btl_tcp_if_include",
                "enp0s1",
            ],
        )


class PipelineTests(unittest.TestCase):
    def test_select_final_value_defaults_to_largest(self):
        self.assertEqual(select_final_value([1, 4, 2], None, "processes"), 4)
        self.assertEqual(select_final_value([1, 4, 2], 2, "processes"), 2)
        with self.assertRaises(ValueError):
            select_final_value([1, 4, 2], 8, "processes")

    def test_build_pipeline_commands_with_skip_sweep(self):
        run_ids, commands = build_pipeline_commands(
            python="python",
            config="configs/local_smoke.json",
            input_sizes=[2],
            process_counts=[1, 2],
            label="mini_sweep",
            output_dir="results",
            report_dir="report",
            final_n=2,
            final_processes=2,
            load_balance_n=None,
            bundle_name="bundle",
            skip_sweep=True,
            benchmark_plan="report/BENCHMARK_PLAN.json",
            sweep_extra=[],
        )

        self.assertEqual(run_ids.serial_run_dir, "results/serial-mini_sweep-N2")
        self.assertEqual(run_ids.mpi_run_dir, "results/mpi-mini_sweep-N2-P2")
        self.assertEqual(run_ids.correctness_report, "results/compare-mini_sweep-N2-P2/correctness_report.json")
        self.assertEqual(run_ids.environment_json, "results/environment-mini_sweep.json")
        self.assertEqual(run_ids.environment_markdown, "report/ENVIRONMENT_mini_sweep.md")
        self.assertEqual(run_ids.ownership_json, "report/TEAM_OWNERSHIP_REPORT.json")
        self.assertEqual(run_ids.ownership_markdown, "report/TEAM_OWNERSHIP_REPORT.md")
        self.assertEqual(run_ids.defense_guide_json, "report/MEMBER_DEFENSE_GUIDE.json")
        self.assertEqual(run_ids.defense_guide_markdown, "report/MEMBER_DEFENSE_GUIDE.md")
        self.assertEqual(run_ids.granularity_json, "results/granularity-mini_sweep-N2-P2.json")
        self.assertEqual(run_ids.granularity_markdown, "report/GRANULARITY_mini_sweep.md")
        self.assertEqual(run_ids.communication_json, "results/communication-mini_sweep-N2-P2.json")
        self.assertEqual(run_ids.communication_markdown, "report/COMMUNICATION_mini_sweep.md")
        self.assertEqual(run_ids.solution_quality_json, "results/solution-quality-mini_sweep-N2-P2.json")
        self.assertEqual(run_ids.solution_quality_markdown, "report/SOLUTION_QUALITY_mini_sweep.md")
        self.assertEqual(run_ids.experiment_index_json, "report/EXPERIMENT_INDEX_mini_sweep.json")
        self.assertEqual(run_ids.experiment_index_markdown, "report/EXPERIMENT_INDEX_mini_sweep.md")
        self.assertEqual(run_ids.report_sync_json, "report/REPORT_SYNC_mini_sweep.json")
        self.assertEqual(run_ids.report_sync_markdown, "report/REPORT_SYNC_mini_sweep.md")
        self.assertEqual(run_ids.results_summary_json, "report/RESULTS_SUMMARY_mini_sweep.json")
        self.assertEqual(run_ids.results_summary_markdown, "report/RESULTS_SUMMARY_mini_sweep.md")
        self.assertEqual(run_ids.benchmark_budget_json, "report/BENCHMARK_BUDGET_mini_sweep.json")
        self.assertEqual(run_ids.benchmark_budget_markdown, "report/BENCHMARK_BUDGET_mini_sweep.md")
        self.assertEqual(run_ids.final_audit_json, "report/FINAL_AUDIT_mini_sweep.json")
        self.assertEqual(run_ids.final_audit_markdown, "report/FINAL_AUDIT_mini_sweep.md")
        self.assertEqual(run_ids.submission_manifest_json, "submission/mini_sweep/SUBMISSION_MANIFEST.json")
        self.assertEqual(run_ids.submission_manifest_markdown, "submission/mini_sweep/SUBMISSION_MANIFEST.md")
        self.assertEqual(run_ids.runtime_figure_name, "runtime_vs_input_size_mini_sweep.png")
        self.assertEqual(run_ids.speedup_figure_name, "speedup_mini_sweep.png")
        self.assertEqual(run_ids.trajectory_gif_name, "trajectory_mini_sweep.gif")
        self.assertEqual(run_ids.trajectory_gif, "report/figures/trajectory_mini_sweep.gif")
        self.assertEqual(run_ids.algorithm_trace_gif_name, "algorithm_trace_mini_sweep.gif")
        self.assertEqual(run_ids.algorithm_trace_gif, "report/figures/algorithm_trace_mini_sweep.gif")
        self.assertEqual(run_ids.algorithm_trace_json, "report/ALGORITHM_TRACE_mini_sweep.json")
        self.assertEqual(run_ids.bundled_rank_breakdown_name, "bundle_mpi_mpi-mini_sweep-N2-P2_rank_time_breakdown.png")
        self.assertFalse(any(command.name == "run sweep" for command in commands))
        self.assertEqual(commands[0].name, "capture environment")
        self.assertEqual(commands[1].name, "generate ownership report")
        self.assertEqual(commands[2].name, "generate member defense guide")
        self.assertEqual(commands[3].name, "estimate benchmark budget")
        validate = next(command for command in commands if command.name == "validate report artifacts")
        animation = next(command for command in commands if command.name == "animate best trajectory")
        algorithm_animation = next(command for command in commands if command.name == "animate algorithm trace")
        budget = next(command for command in commands if command.name == "estimate benchmark budget")
        report_sync = next(command for command in commands if command.name == "check report sync")
        results_summary = next(command for command in commands if command.name == "export results summary")
        audit = next(command for command in commands if command.name == "audit final experiment readiness")
        submission = commands[-1]
        self.assertEqual(audit.name, "audit final experiment readiness")
        self.assertEqual(submission.name, "export submission package")
        self.assertLess(commands.index(budget), commands.index(validate))
        self.assertLess(commands.index(results_summary), commands.index(validate))
        self.assertIn("--required-figure", validate.command)
        self.assertIn("--environment", validate.command)
        self.assertIn("--granularity", validate.command)
        self.assertIn("--communication", validate.command)
        self.assertIn("--solution-quality", validate.command)
        self.assertIn("--ownership", validate.command)
        self.assertIn("--defense-guide", validate.command)
        self.assertIn("--experiment-index", validate.command)
        self.assertIn("--report-sync", validate.command)
        self.assertIn("--results-summary", validate.command)
        self.assertIn("--benchmark-plan", validate.command)
        self.assertIn("--benchmark-budget", validate.command)
        self.assertIn("scripts/estimate_benchmark_budget.py", budget.command)
        self.assertIn("report/BENCHMARK_BUDGET_mini_sweep.json", budget.command)
        self.assertIn("--run-label", budget.command)
        self.assertIn("--results-dir", budget.command)
        self.assertIn("results", budget.command)
        self.assertNotIn("--reuse-existing", budget.command)
        self.assertIn("scripts/animate_trajectory.py", animation.command)
        self.assertIn("report/figures/trajectory_mini_sweep.gif", animation.command)
        self.assertIn("scripts/animate_algorithm_trace.py", algorithm_animation.command)
        self.assertIn("report/figures/algorithm_trace_mini_sweep.gif", algorithm_animation.command)
        self.assertIn("report/ALGORITHM_TRACE_mini_sweep.json", algorithm_animation.command)
        self.assertIn("scripts/check_report_sync.py", report_sync.command)
        self.assertIn("report/REPORT_SYNC_mini_sweep.json", report_sync.command)
        self.assertIn("scripts/export_results_summary.py", results_summary.command)
        self.assertIn("report/RESULTS_SUMMARY_mini_sweep.json", results_summary.command)
        self.assertIn("report/figures/algorithm_trace_mini_sweep.gif", results_summary.command)
        self.assertIn("--speedup-n", audit.command)
        self.assertIn("results/communication-mini_sweep-N2-P2.json", audit.command)
        self.assertIn("results/solution-quality-mini_sweep-N2-P2.json", audit.command)
        self.assertIn("report/TEAM_OWNERSHIP_REPORT.json", audit.command)
        self.assertIn("report/MEMBER_DEFENSE_GUIDE.json", audit.command)
        self.assertIn("report/FINAL_AUDIT_mini_sweep.json", audit.command)
        self.assertIn("--benchmark-plan", audit.command)
        self.assertIn("scripts/export_submission_package.py", submission.command)
        self.assertIn("--label", submission.command)
        self.assertIn("mini_sweep", submission.command)

    def test_build_pipeline_commands_includes_sweep_and_extra_args(self):
        _, commands = build_pipeline_commands(
            python="python",
            config="configs/local_smoke.json",
            input_sizes=[2, 4],
            process_counts=[1, 2],
            label="unit",
            output_dir="results",
            report_dir="report",
            final_n=4,
            final_processes=2,
            load_balance_n=2,
            bundle_name="unit",
            skip_sweep=False,
            skip_existing_runs=True,
            benchmark_plan="report/BENCHMARK_PLAN.json",
            sweep_extra=["--max-outer-iters", "4"],
        )

        sweep = next(command for command in commands if command.name == "run sweep")
        budget = next(command for command in commands if command.name == "estimate benchmark budget")
        self.assertIn("--skip-existing", sweep.command)
        self.assertIn("--max-outer-iters", sweep.command)
        self.assertIn("4", sweep.command)
        self.assertIn("--reuse-existing", budget.command)
        self.assertIn("--max-outer-iters", budget.command)
        self.assertIn("4", budget.command)
        tables = next(command for command in commands if command.name == "export report tables")
        self.assertIn("results/mpi-unit-N2-P2", tables.command)
        bundle = next(command for command in commands if command.name == "export report artifact bundle")
        self.assertEqual(bundle.command.count("--mpi-run"), 2)


class BenchmarkBudgetTests(unittest.TestCase):
    def _write_plan(self, path: Path):
        payload = {
            "label": "unit_plan",
            "config": "configs/local_benchmark.json",
            "seconds_per_task": 0.5,
            "assumed_parallel_efficiency": 0.75,
            "input_sizes": [10, 20],
            "process_counts": [1, 2],
            "pipeline_command": ["python", "scripts/run_local_pipeline.py", "--label", "unit"],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_budget_passes_for_reasonable_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "BENCHMARK_PLAN.json"
            self._write_plan(plan)

            payload = build_benchmark_budget(plan, max_total_seconds=120.0, label="unit")

            self.assertTrue(payload["passed"], payload["warnings"])
            self.assertEqual(payload["num_rows"], 6)
            self.assertGreater(payload["estimated_total_seconds"], 0.0)
            self.assertIn("not final benchmark data", benchmark_budget_markdown(payload))

            json_path, markdown_path = write_benchmark_budget(
                payload,
                root / "BENCHMARK_BUDGET_unit.json",
                root / "BENCHMARK_BUDGET_unit.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            items = validate_benchmark_budget(json_path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])

    def test_budget_reuse_existing_counts_only_missing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "experiment_name": "unit",
                        "output_dir": str(root / "results"),
                        "total_tasks": 2,
                    }
                ),
                encoding="utf-8",
            )
            plan = root / "BENCHMARK_PLAN.json"
            plan.write_text(
                json.dumps(
                    {
                        "label": "unit",
                        "config": str(config),
                        "seconds_per_task": 1.0,
                        "assumed_parallel_efficiency": 1.0,
                        "input_sizes": [2],
                        "process_counts": [1, 2],
                        "pipeline_command": ["python", "scripts/run_local_pipeline.py", "--label", "unit"],
                    }
                ),
                encoding="utf-8",
            )
            results_dir = root / "results"
            expected = expected_run_metadata(
                config_path=config,
                output_dir=str(results_dir),
                label="unit",
                input_size_n=2,
                mode="serial",
                processes=1,
            )
            run_dir = results_dir / expected["run_id"]
            run_dir.mkdir(parents=True)
            (run_dir / "summary.json").write_text(json.dumps(expected), encoding="utf-8")

            payload = build_benchmark_budget(
                plan,
                max_total_seconds=120.0,
                label="unit",
                results_dir=results_dir,
                reuse_existing=True,
                run_label="unit",
            )

            serial_row = next(row for row in payload["rows"] if row["kind"] == "serial")
            self.assertEqual(serial_row["status"], "reusable")
            self.assertEqual(serial_row["remaining_seconds"], 0.0)
            self.assertEqual(payload["num_reusable_rows"], 1)
            self.assertEqual(payload["num_remaining_rows"], 2)
            self.assertLess(payload["estimated_remaining_seconds"], payload["estimated_total_seconds"])
            self.assertIn("Estimated remaining time", benchmark_budget_markdown(payload))

    def test_budget_fails_when_total_is_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "BENCHMARK_PLAN.json"
            self._write_plan(plan)

            payload = build_benchmark_budget(plan, max_total_seconds=1.0, label="unit")

            self.assertFalse(payload["passed"])
            self.assertTrue(payload["warnings"])


class BenchmarkPlanTests(unittest.TestCase):
    def test_rounding_and_process_counts(self):
        self.assertEqual(round_up_to_multiple(17, 4), 20)
        self.assertEqual(process_counts_for_max(10), [1, 2, 4, 8, 10])
        self.assertEqual(process_counts_for_max(8), [1, 2, 4, 8])
        self.assertEqual(input_sizes_from_n(20, 40, [0.5, 1.0], 4), [12, 20, 40])

    def test_create_benchmark_plan_from_seconds_per_task(self):
        plan = create_benchmark_plan(
            config="configs/local_benchmark.json",
            label="unit_plan",
            target_seconds=100.0,
            target_processes=4,
            assumed_parallel_efficiency=0.5,
            seconds_per_task=10.0,
            runtime_factors=[0.5, 1.0],
        )

        self.assertEqual(plan.chosen_n, 20)
        self.assertEqual(plan.speedup_n, 40)
        self.assertEqual(plan.process_counts, [1, 2, 4])
        self.assertIn("--load-balance-n", plan.pipeline_command)
        self.assertIn("20", plan.pipeline_command)
        self.assertIn("--final-n", plan.pipeline_command)
        self.assertIn("40", plan.pipeline_command)

    def test_benchmark_plan_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = create_benchmark_plan(
                config="configs/local_benchmark.json",
                label="unit_plan",
                target_seconds=100.0,
                target_processes=4,
                assumed_parallel_efficiency=0.5,
                seconds_per_task=10.0,
                runtime_factors=[0.5, 1.0],
            )
            path = root / "plan.json"
            path.write_text(json.dumps(plan.to_json()), encoding="utf-8")
            items = validate_benchmark_plan(path)
            self.assertTrue(all(item.passed for item in items), [item.to_json() for item in items])


class BenchmarkScenarioTests(unittest.TestCase):
    def test_scenarios_compare_safe_and_strict_targets(self):
        payload = build_benchmark_scenarios(
            config="configs/local_benchmark.json",
            label="unit",
            target_seconds=[60.0, 150.0],
            target_processes=4,
            assumed_parallel_efficiency=0.75,
            seconds_per_task=0.5,
            runtime_factors=[0.5, 1.0, 2.0],
            scenario_names=["safe", "strict"],
        )

        self.assertEqual(len(payload["scenarios"]), 2)
        safe, strict = payload["scenarios"]
        self.assertLess(safe["chosen_n"], strict["chosen_n"])
        self.assertIn("--skip-existing-runs", safe["pipeline_command"])
        self.assertIn("Scenario estimates are planning data", payload["note"])
        self.assertIn("Benchmark Scenario Comparison", benchmark_scenarios_markdown(payload))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path, markdown_path = write_benchmark_scenarios(
                payload,
                root / "scenarios.json",
                root / "scenarios.md",
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())


class ClusterPlanTests(unittest.TestCase):
    def _inventory(self):
        return {
            "cluster_name": "unit_cluster",
            "default_user": "ubuntu",
            "default_repo_dir": "/home/ubuntu/mpot",
            "default_venv_python": "/home/ubuntu/mpot/.venv/bin/python",
            "hosts": [
                {"name": "mpot-a", "address": "192.168.1.101", "slots": 4},
                {"name": "mpot-b", "address": "192.168.1.102", "slots": 4},
            ],
        }

    def test_cluster_hostfile_and_commands(self):
        hosts = parse_hosts(self._inventory())
        text = hostfile_text(hosts)

        self.assertIn("192.168.1.101 slots=4", text)
        self.assertIn("mpot-b", text)

    def test_cluster_plan_writes_hostfile_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / "cluster.json"
            inventory.write_text(json.dumps(self._inventory()), encoding="utf-8")
            payload = build_cluster_plan(
                inventory,
                hostfile_path=root / "hostfile.txt",
                total_processes=8,
                smoke_tasks=8,
            )

            self.assertEqual(payload["total_slots"], 8)
            self.assertIn("--hostfile", payload["commands"]["mpi_probe"])
            self.assertIn("scripts/run_sweep.py", payload["commands"]["sweep_smoke"])
            self.assertIn("Ubuntu VM Cluster Plan", cluster_plan_markdown(payload))

            hostfile_path, json_path, markdown_path = write_cluster_plan(
                payload,
                hostfile_path=root / "hostfile.txt",
                json_path=root / "cluster_plan.json",
                markdown_path=root / "cluster_plan.md",
            )
            self.assertTrue(hostfile_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())


if __name__ == "__main__":
    unittest.main()
