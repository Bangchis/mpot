"""Tkinter GUI for editing and running the 2D MPOT/OpenMPI demo."""

from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import platform
import subprocess
import time

from mpot.benchmarks.animation import animate_algorithm_trace, animate_best_path, animate_parallel_schedule
from mpot.benchmarks.config import ExperimentConfig, load_config
from mpot.benchmarks.gui_support import (
    GuiObstacle,
    GuiRunOptions,
    GuiScene,
    build_config_from_gui,
    build_mpi_command,
    expected_run_dir,
    options_from_config,
    scene_from_config,
    write_gui_config,
)


class MpotGuiApp:
    """Small drag-and-drop GUI for the course 2D motion-planning demo."""

    canvas_size = 560
    canvas_pad = 30

    def __init__(self, root, *, base_config_path: str | Path, repo_root: str | Path):
        self.tk, self.ttk = _load_tk()
        self.root = root
        self.repo_root = Path(repo_root).resolve()
        self.base_config_path = Path(base_config_path).resolve()
        self.base_config: ExperimentConfig = load_config(self.base_config_path)
        self.scene: GuiScene = scene_from_config(self.base_config)
        self.options: GuiRunOptions = options_from_config(
            self.base_config,
            mpi_processes=4,
            run_id=f"gui-mpot-{time.strftime('%Y%m%d-%H%M%S')}",
        )
        self.mode = self.tk.StringVar(value="drag")
        self.selected_obstacle_index: int | None = None
        self.drag_target: tuple[str, int | None] | None = None
        self.queue: Queue[tuple[str, str]] = Queue()
        self.running = False
        self.last_run_dir: Path | None = None
        self.entries: dict[str, object] = {}
        self.obstacle_entries: dict[str, object] = {}

        self.root.title("MPOT 2D Parallel Motion Planning GUI")
        self.root.geometry("1180x820")
        self._build_layout()
        self._redraw_canvas()
        self._poll_queue()

    def _build_layout(self) -> None:
        tk = self.tk
        ttk = self.ttk
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(outer)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        right = ttk.Frame(outer)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self.canvas = tk.Canvas(left, width=self.canvas_size, height=self.canvas_size, bg="#f7f8fb", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=False)
        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)

        tool_frame = ttk.LabelFrame(left, text="Scene tools", padding=8)
        tool_frame.pack(fill=tk.X, pady=(10, 0))
        for label, value in [
            ("Drag/select", "drag"),
            ("Add obstacle", "add_obstacle"),
            ("Set start", "set_start"),
            ("Set goal", "set_goal"),
        ]:
            ttk.Radiobutton(tool_frame, text=label, value=value, variable=self.mode).pack(side=tk.LEFT, padx=3)
        ttk.Button(tool_frame, text="Delete selected", command=self._delete_selected_obstacle).pack(side=tk.LEFT, padx=8)
        ttk.Button(tool_frame, text="Reset scene", command=self._reset_scene).pack(side=tk.LEFT, padx=3)

        obstacle_frame = ttk.LabelFrame(left, text="Selected obstacle", padding=8)
        obstacle_frame.pack(fill=tk.X, pady=(10, 0))
        self._add_obstacle_entry(obstacle_frame, "radius", "Radius", 0, 0)
        self._add_obstacle_entry(obstacle_frame, "safety_margin", "Safety margin", 0, 2)
        ttk.Button(obstacle_frame, text="Apply obstacle values", command=self._apply_selected_obstacle_values).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0)
        )

        params = ttk.LabelFrame(right, text="Run parameters", padding=10)
        params.pack(fill=tk.X)
        self._add_entry(params, "run_id", "Run id", self.options.run_id, 0, 0, width=28)
        self._add_entry(params, "experiment_name", "Experiment", self.options.experiment_name, 0, 2, width=22)
        self._add_entry(params, "total_tasks", "N tasks", self.options.total_tasks, 1, 0)
        self._add_entry(params, "mpi_processes", "MPI ranks P", self.options.mpi_processes, 1, 2)
        self._add_entry(params, "base_seed", "Base seed", self.options.base_seed, 2, 0)
        self._add_entry(params, "traj_len", "Trajectory length", self.options.traj_len, 2, 2)
        self._add_entry(params, "num_particles", "Particles/task", self.options.num_particles, 3, 0)
        self._add_entry(params, "num_probe", "Probe samples", self.options.num_probe, 3, 2)
        self._add_entry(params, "step_radius", "Step radius", self.options.step_radius, 4, 0)
        self._add_entry(params, "probe_radius", "Probe radius", self.options.probe_radius, 4, 2)
        self._add_entry(params, "max_outer_iters", "Outer iters", self.options.max_outer_iters, 5, 0)
        self._add_entry(params, "max_inner_iters", "Sinkhorn inner", self.options.max_inner_iters, 5, 2)
        self._add_entry(params, "trace_fps", "GIF fps", self.options.trace_fps, 6, 0)
        self._add_entry(params, "trace_max_particles", "Particles shown", self.options.trace_max_particles, 6, 2)

        ttk.Label(params, text="Probe type").grid(row=7, column=0, sticky="w", pady=3)
        self.polytope_var = tk.StringVar(value=self.options.polytope)
        ttk.OptionMenu(params, self.polytope_var, self.options.polytope, "orthoplex", "cube", "simplex").grid(
            row=7, column=1, sticky="ew", pady=3
        )

        costs = ttk.LabelFrame(right, text="Cost weights", padding=10)
        costs.pack(fill=tk.X, pady=(10, 0))
        self._add_entry(costs, "obstacle_weight", "Obstacle", self.options.obstacle_weight, 0, 0)
        self._add_entry(costs, "goal_weight", "Goal", self.options.goal_weight, 0, 2)
        self._add_entry(costs, "smoothness_weight", "Smoothness", self.options.smoothness_weight, 1, 0)
        self._add_entry(costs, "boundary_weight", "Boundary", self.options.boundary_weight, 1, 2)
        self._add_entry(costs, "velocity_weight", "Velocity", self.options.velocity_weight, 2, 0)

        actions = ttk.Frame(right)
        actions.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(actions, text="Fast defaults", command=self._apply_fast_defaults).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="Detailed defaults", command=self._apply_detailed_defaults).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Save config only", command=self._save_config_only).pack(side=tk.LEFT, padx=6)
        self.run_button = ttk.Button(actions, text="Run MPI + GIFs", command=self._start_run)
        self.run_button.pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Open output folder", command=self._open_last_run_dir).pack(side=tk.LEFT, padx=6)

        output_frame = ttk.LabelFrame(right, text="Output log", padding=8)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(output_frame, height=18, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(output_frame, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set)
        self._log("Ready. Drag start/goal/obstacles, choose parameters, then run MPI + GIFs.")

    def _add_entry(self, parent, key: str, label: str, value, row: int, col: int, width: int = 12) -> None:
        ttk = self.ttk
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=3, padx=(0, 4))
        var = self.tk.StringVar(value=str(value))
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=col + 1, sticky="ew", pady=3, padx=(0, 12))
        parent.columnconfigure(col + 1, weight=1)
        self.entries[key] = var

    def _add_obstacle_entry(self, parent, key: str, label: str, row: int, col: int) -> None:
        self.ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=3, padx=(0, 4))
        var = self.tk.StringVar(value="")
        self.ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=col + 1, sticky="ew", pady=3)
        self.obstacle_entries[key] = var

    def _world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        xmin, ymin = self.scene.workspace_min
        xmax, ymax = self.scene.workspace_max
        span = self.canvas_size - 2 * self.canvas_pad
        cx = self.canvas_pad + (x - xmin) / (xmax - xmin) * span
        cy = self.canvas_pad + (ymax - y) / (ymax - ymin) * span
        return cx, cy

    def _canvas_to_world(self, cx: float, cy: float) -> tuple[float, float]:
        xmin, ymin = self.scene.workspace_min
        xmax, ymax = self.scene.workspace_max
        span = self.canvas_size - 2 * self.canvas_pad
        x = xmin + (cx - self.canvas_pad) / span * (xmax - xmin)
        y = ymax - (cy - self.canvas_pad) / span * (ymax - ymin)
        return self._clamp_point(x, y)

    def _world_radius_to_canvas(self, radius: float) -> float:
        xmin, _ = self.scene.workspace_min
        xmax, _ = self.scene.workspace_max
        span = self.canvas_size - 2 * self.canvas_pad
        return radius / (xmax - xmin) * span

    def _clamp_point(self, x: float, y: float) -> tuple[float, float]:
        xmin, ymin = self.scene.workspace_min
        xmax, ymax = self.scene.workspace_max
        return max(xmin, min(xmax, x)), max(ymin, min(ymax, y))

    def _redraw_canvas(self) -> None:
        tk = self.tk
        self.canvas.delete("all")
        self.canvas.create_rectangle(
            self.canvas_pad,
            self.canvas_pad,
            self.canvas_size - self.canvas_pad,
            self.canvas_size - self.canvas_pad,
            outline="#222222",
            width=2,
            fill="#ffffff",
        )
        for i in range(5):
            offset = self.canvas_pad + i * (self.canvas_size - 2 * self.canvas_pad) / 4
            self.canvas.create_line(offset, self.canvas_pad, offset, self.canvas_size - self.canvas_pad, fill="#e8edf3")
            self.canvas.create_line(self.canvas_pad, offset, self.canvas_size - self.canvas_pad, offset, fill="#e8edf3")

        for index, obstacle in enumerate(self.scene.obstacles):
            cx, cy = self._world_to_canvas(obstacle.x, obstacle.y)
            hard = self._world_radius_to_canvas(obstacle.radius)
            soft = self._world_radius_to_canvas(obstacle.radius + obstacle.safety_margin)
            tag = f"obstacle:{index}"
            selected = index == self.selected_obstacle_index
            self.canvas.create_oval(
                cx - soft,
                cy - soft,
                cx + soft,
                cy + soft,
                fill="#f28e2b",
                outline="#f28e2b",
                stipple="gray25",
                tags=(tag, "obstacle"),
            )
            self.canvas.create_oval(
                cx - hard,
                cy - hard,
                cx + hard,
                cy + hard,
                fill="#222222",
                outline="#0057b8" if selected else "#000000",
                width=3 if selected else 1,
                tags=(tag, "obstacle"),
            )
            self.canvas.create_text(cx, cy, text=str(index + 1), fill="white", font=("TkDefaultFont", 10, "bold"), tags=(tag, "obstacle"))

        sx, sy = self._world_to_canvas(self.scene.start[0], self.scene.start[1])
        gx, gy = self._world_to_canvas(self.scene.goal[0], self.scene.goal[1])
        self.canvas.create_oval(sx - 10, sy - 10, sx + 10, sy + 10, fill="#2ca02c", outline="#145a1f", width=2, tags=("start",))
        self.canvas.create_text(sx, sy - 18, text="START", fill="#145a1f", tags=("start",))
        self.canvas.create_polygon(
            gx,
            gy - 13,
            gx + 13,
            gy,
            gx,
            gy + 13,
            gx - 13,
            gy,
            fill="#d62728",
            outline="#7f1d1d",
            width=2,
            tags=("goal",),
        )
        self.canvas.create_text(gx, gy - 21, text="GOAL", fill="#7f1d1d", tags=("goal",))
        self.canvas.create_text(
            14,
            self.canvas_size - 14,
            anchor=tk.SW,
            fill="#555555",
            text="Double-click: add obstacle | drag circles/markers to edit scene",
        )

    def _tag_at_event(self, event) -> tuple[str, int | None] | None:
        items = self.canvas.find_overlapping(event.x - 4, event.y - 4, event.x + 4, event.y + 4)
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            if "start" in tags:
                return ("start", None)
            if "goal" in tags:
                return ("goal", None)
            for tag in tags:
                if tag.startswith("obstacle:"):
                    return ("obstacle", int(tag.split(":", 1)[1]))
        return None

    def _on_canvas_press(self, event) -> None:
        x, y = self._canvas_to_world(event.x, event.y)
        mode = self.mode.get()
        if mode == "add_obstacle":
            self.scene.obstacles.append(GuiObstacle(x=x, y=y))
            self.selected_obstacle_index = len(self.scene.obstacles) - 1
            self._sync_obstacle_fields()
            self._redraw_canvas()
            return
        if mode == "set_start":
            self.scene.start[0], self.scene.start[1] = x, y
            self._redraw_canvas()
            return
        if mode == "set_goal":
            self.scene.goal[0], self.scene.goal[1] = x, y
            self._redraw_canvas()
            return
        target = self._tag_at_event(event)
        self.drag_target = target
        if target and target[0] == "obstacle":
            self.selected_obstacle_index = target[1]
            self._sync_obstacle_fields()
        self._redraw_canvas()

    def _on_canvas_drag(self, event) -> None:
        if not self.drag_target:
            return
        x, y = self._canvas_to_world(event.x, event.y)
        kind, index = self.drag_target
        if kind == "start":
            self.scene.start[0], self.scene.start[1] = x, y
        elif kind == "goal":
            self.scene.goal[0], self.scene.goal[1] = x, y
        elif kind == "obstacle" and index is not None and 0 <= index < len(self.scene.obstacles):
            self.scene.obstacles[index].x = x
            self.scene.obstacles[index].y = y
        self._redraw_canvas()

    def _on_canvas_release(self, _event) -> None:
        self.drag_target = None

    def _on_canvas_double_click(self, event) -> None:
        x, y = self._canvas_to_world(event.x, event.y)
        self.scene.obstacles.append(GuiObstacle(x=x, y=y))
        self.selected_obstacle_index = len(self.scene.obstacles) - 1
        self._sync_obstacle_fields()
        self._redraw_canvas()

    def _sync_obstacle_fields(self) -> None:
        if self.selected_obstacle_index is None or self.selected_obstacle_index >= len(self.scene.obstacles):
            for var in self.obstacle_entries.values():
                var.set("")
            return
        obstacle = self.scene.obstacles[self.selected_obstacle_index]
        self.obstacle_entries["radius"].set(f"{obstacle.radius:.3f}")
        self.obstacle_entries["safety_margin"].set(f"{obstacle.safety_margin:.3f}")

    def _apply_selected_obstacle_values(self) -> None:
        if self.selected_obstacle_index is None or self.selected_obstacle_index >= len(self.scene.obstacles):
            self._log("No obstacle selected.")
            return
        try:
            radius = float(self.obstacle_entries["radius"].get())
            margin = float(self.obstacle_entries["safety_margin"].get())
            if radius <= 0 or margin < 0:
                raise ValueError
        except ValueError:
            self._log("Obstacle radius must be > 0 and safety margin must be >= 0.")
            return
        obstacle = self.scene.obstacles[self.selected_obstacle_index]
        obstacle.radius = radius
        obstacle.safety_margin = margin
        self._redraw_canvas()

    def _delete_selected_obstacle(self) -> None:
        if self.selected_obstacle_index is None:
            self._log("No obstacle selected.")
            return
        if 0 <= self.selected_obstacle_index < len(self.scene.obstacles):
            del self.scene.obstacles[self.selected_obstacle_index]
        self.selected_obstacle_index = None
        self._sync_obstacle_fields()
        self._redraw_canvas()

    def _reset_scene(self) -> None:
        self.scene = scene_from_config(self.base_config)
        self.selected_obstacle_index = None
        self._sync_obstacle_fields()
        self._redraw_canvas()
        self._log("Scene reset from base config.")

    def _apply_fast_defaults(self) -> None:
        values = {
            "total_tasks": 4,
            "mpi_processes": 2,
            "num_particles": 6,
            "num_probe": 2,
            "traj_len": 24,
            "max_outer_iters": 6,
            "max_inner_iters": 18,
            "trace_max_particles": 12,
        }
        self._set_entries(values)
        self.polytope_var.set("orthoplex")
        self._log("Applied fast defaults for a quick demo.")

    def _apply_detailed_defaults(self) -> None:
        values = {
            "total_tasks": 12,
            "mpi_processes": 4,
            "num_particles": 16,
            "num_probe": 4,
            "traj_len": 32,
            "max_outer_iters": 12,
            "max_inner_iters": 28,
            "trace_max_particles": 24,
        }
        self._set_entries(values)
        self.polytope_var.set("orthoplex")
        self._log("Applied detailed defaults. This gives a richer GIF but takes longer.")

    def _set_entries(self, values: dict[str, object]) -> None:
        for key, value in values.items():
            if key in self.entries:
                self.entries[key].set(str(value))

    def _read_options(self) -> GuiRunOptions:
        def text(key: str) -> str:
            return str(self.entries[key].get()).strip()

        def as_int(key: str) -> int:
            return int(text(key))

        def as_float(key: str) -> float:
            return float(text(key))

        return GuiRunOptions(
            run_id=text("run_id"),
            experiment_name=text("experiment_name"),
            output_dir=self.options.output_dir,
            total_tasks=as_int("total_tasks"),
            mpi_processes=as_int("mpi_processes"),
            base_seed=as_int("base_seed"),
            traj_len=as_int("traj_len"),
            num_particles=as_int("num_particles"),
            num_probe=as_int("num_probe"),
            polytope=self.polytope_var.get(),
            step_radius=as_float("step_radius"),
            probe_radius=as_float("probe_radius"),
            max_outer_iters=as_int("max_outer_iters"),
            min_outer_iters=self.options.min_outer_iters,
            max_inner_iters=as_int("max_inner_iters"),
            obstacle_weight=as_float("obstacle_weight"),
            smoothness_weight=as_float("smoothness_weight"),
            goal_weight=as_float("goal_weight"),
            boundary_weight=as_float("boundary_weight"),
            velocity_weight=as_float("velocity_weight"),
            trace_fps=as_int("trace_fps"),
            trace_max_particles=as_int("trace_max_particles"),
        )

    def _build_effective_config(self) -> tuple[ExperimentConfig, GuiRunOptions]:
        options = self._read_options()
        if not options.run_id:
            raise ValueError("Run id cannot be empty.")
        if options.mpi_processes <= 0:
            raise ValueError("MPI ranks P must be positive.")
        if options.trace_fps <= 0:
            raise ValueError("GIF fps must be positive.")
        config = build_config_from_gui(self.base_config, self.scene, options)
        return config, options

    def _save_config_only(self) -> None:
        try:
            config, options = self._build_effective_config()
            path = write_gui_config(config, options.run_id, config_dir=self.repo_root / "results" / "gui_configs")
        except Exception as exc:
            self._log(f"Config save failed: {exc}")
            return
        self._log(f"Saved GUI config: {path}")

    def _start_run(self) -> None:
        if self.running:
            self._log("A run is already in progress.")
            return
        try:
            config, options = self._build_effective_config()
            config_path = write_gui_config(config, options.run_id, config_dir=self.repo_root / "results" / "gui_configs")
        except Exception as exc:
            self._log(f"Cannot start run: {exc}")
            return

        self.options = options
        self.running = True
        self.run_button.configure(state="disabled")
        self._log(f"Saved config: {config_path}")
        worker = Thread(target=self._run_worker, args=(config_path, options), daemon=True)
        worker.start()

    def _run_worker(self, config_path: Path, options: GuiRunOptions) -> None:
        try:
            command = build_mpi_command(config_path, options.run_id, options.mpi_processes)
            self.queue.put(("log", "$ " + " ".join(command)))
            process = subprocess.Popen(
                command,
                cwd=self.repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.queue.put(("log", line.rstrip()))
            returncode = process.wait()
            if returncode != 0:
                self.queue.put(("error", f"MPI run failed with exit code {returncode}."))
                return

            run_dir = self.repo_root / expected_run_dir(options)
            self.queue.put(("log", f"MPI run complete: {run_dir}"))
            self.queue.put(("log", "Generating best-path GIF..."))
            best_gif = animate_best_path(run_dir, output=run_dir / "best_path.gif", fps=8)
            self.queue.put(("log", f"wrote {best_gif}"))
            self.queue.put(("log", "Generating MPOT iteration trace GIF..."))
            trace_gif = animate_algorithm_trace(
                run_dir,
                output=run_dir / "algorithm_trace.gif",
                trace_output=run_dir / "algorithm_trace.json",
                fps=options.trace_fps,
                max_particles=options.trace_max_particles,
            )
            self.queue.put(("log", f"wrote {trace_gif}"))
            self.queue.put(("log", "Generating MPI parallel schedule GIF..."))
            schedule_gif = animate_parallel_schedule(run_dir, output=run_dir / "parallel_schedule.gif", fps=1)
            self.queue.put(("log", f"wrote {schedule_gif}"))
            self.queue.put(("done", str(run_dir)))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, message = self.queue.get_nowait()
                if kind == "log":
                    self._log(message)
                elif kind == "error":
                    self._log(f"ERROR: {message}")
                    self.running = False
                    self.run_button.configure(state="normal")
                elif kind == "done":
                    self.last_run_dir = Path(message)
                    self._log("Done. Output GIFs:")
                    self._log(f"- {self.last_run_dir / 'best_path.gif'}")
                    self._log(f"- {self.last_run_dir / 'algorithm_trace.gif'}")
                    self._log(f"- {self.last_run_dir / 'parallel_schedule.gif'}")
                    self.running = False
                    self.run_button.configure(state="normal")
        except Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _log(self, message: str) -> None:
        self.log_text.insert(self.tk.END, message + "\n")
        self.log_text.see(self.tk.END)

    def _open_last_run_dir(self) -> None:
        if self.last_run_dir is None:
            candidate = self.repo_root / expected_run_dir(self.options)
            if candidate.exists():
                self.last_run_dir = candidate
            else:
                self._log("No completed GUI run directory yet.")
                return
        path = str(self.last_run_dir)
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["open", path])
            elif system == "Windows":
                subprocess.Popen(["explorer", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            self._log(f"Could not open output folder: {exc}")


def _load_tk():
    import tkinter as tk
    from tkinter import ttk

    return tk, ttk


def launch_gui(*, base_config_path: str | Path, repo_root: str | Path) -> None:
    """Start the Tkinter GUI."""

    tk, _ = _load_tk()
    root = tk.Tk()
    MpotGuiApp(root, base_config_path=base_config_path, repo_root=repo_root)
    root.mainloop()
