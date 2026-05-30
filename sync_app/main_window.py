# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Main window — full assembly with screen stack, worker management, resume detection."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QToolButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from config import Config
from services.models import CompareMode, ComparisonEntry, ConflictPolicy, ExclusionPreset, ScanResult, SyncAction, SyncDirection, SyncPlan, SyncReport, VerifyMode
from services.sync_state_manager import SyncStateManager
from sync_app.styles.design_system import DesignSystem
from sync_app.styles.icons import icon_manager
from sync_app.workers.scan_worker import ScanWorker
from sync_app.workers.compare_worker import CompareWorker
from sync_app.workers.hash_worker import HashWorker
from sync_app.workers.sync_worker import SyncWorker
from sync_app.workers.resource_monitor_worker import ResourceMonitorWorker
from utils.i18n import tr
from utils.format_utils import format_size
from utils.logger import get_logger
from utils.settings_manager import settings_manager


class MainWindow(QMainWindow):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logger = get_logger()
        self.setWindowTitle(f"{Config.APP_NAME} {Config.get_full_version()}")
        self.setMinimumSize(900, 600)

        self._active_worker: Optional[ScanWorker | CompareWorker | HashWorker | SyncWorker] = None
        self._resource_monitor: Optional[ResourceMonitorWorker] = None
        self._sync_state_manager: Optional[SyncStateManager] = None

        self._source_worker: Optional[ScanWorker] = None
        self._dest_worker: Optional[ScanWorker] = None
        self._compare_worker: Optional[CompareWorker] = None
        self._hash_worker: Optional[HashWorker] = None
        self._hash_path_to_entries: dict[str, list] = {}

        self._current_source = ""
        self._current_dest = ""
        self._source_entries: list = []
        self._dest_entries: list = []
        self._comparison_entries: list[ComparisonEntry] = []
        self._sync_plan: Optional[SyncPlan] = None
        self._last_sync_report: Optional[SyncReport] = None
        self._sync_failed_rel_paths: list[str] = []

        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QVBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._main_layout.addWidget(self._create_header())

        self._stack = QStackedWidget()
        self._main_layout.addWidget(self._stack, stretch=1)

        self._setup_screen = None
        self._analysis_screen = None
        self._review_screen = None
        self._conflict_assistant = None
        self._execution_screen = None
        self._summary_screen = None
        self._snapshots_screen = None
        self._settings_dialog = None
        self._about_dialog = None
        self._resume_dialog = None

        self._init_screens_lazy()

    def _init_screens_lazy(self) -> None:
        self.show_setup()

    def _ensure_screen(self, screen_class, *args, **kwargs):
        from sync_app.screens.setup_screen import SetupScreen
        from sync_app.screens.analysis_screen import AnalysisScreen
        from sync_app.screens.review_screen import ReviewScreen
        from sync_app.screens.conflict_assistant import ConflictAssistant
        from sync_app.screens.execution_screen import ExecutionScreen
        from sync_app.screens.summary_screen import SummaryScreen
        from sync_app.screens.snapshots_screen import SnapshotsScreen

        screen_map = {
            'setup': (SetupScreen, '_setup_screen'),
            'analysis': (AnalysisScreen, '_analysis_screen'),
            'review': (ReviewScreen, '_review_screen'),
            'conflict': (ConflictAssistant, '_conflict_assistant'),
            'execution': (ExecutionScreen, '_execution_screen'),
            'summary': (SummaryScreen, '_summary_screen'),
            'snapshots': (SnapshotsScreen, '_snapshots_screen'),
        }

        if screen_class not in screen_map:
            return None

        cls, attr = screen_map[screen_class]
        screen = getattr(self, attr, None)
        if screen is None:
            screen = cls(**kwargs) if kwargs else cls()
            setattr(self, attr, screen)
            idx = self._stack.addWidget(screen)
            self._connect_screen_signals(screen, screen_class)
        return screen

    def _connect_screen_signals(self, screen, name: str) -> None:
        from sync_app.screens.setup_screen import SetupScreen
        from sync_app.screens.analysis_screen import AnalysisScreen
        from sync_app.screens.review_screen import ReviewScreen
        from sync_app.screens.execution_screen import ExecutionScreen
        from sync_app.screens.summary_screen import SummaryScreen
        from sync_app.screens.conflict_assistant import ConflictAssistant

        if isinstance(screen, SetupScreen):
            screen.analyze_requested.connect(self._on_analyze)
        elif isinstance(screen, AnalysisScreen):
            screen.cancel_requested.connect(self._on_cancel_worker)
        elif isinstance(screen, ReviewScreen):
            screen.sync_requested.connect(self._on_review_sync)
            screen.resolve_conflicts_requested.connect(self._on_resolve_conflicts)
            screen.back_requested.connect(self.show_setup)
            screen.execute_requested.connect(self._on_execute)
            screen.dry_run_requested.connect(self._on_dry_run)
            screen.save_session_requested.connect(self._on_save_session)
            screen.load_session_requested.connect(self._on_load_session)
        elif isinstance(screen, ConflictAssistant):
            screen.all_resolved.connect(self._on_conflicts_resolved)
            screen.back_requested.connect(self._on_resolve_conflicts_back)
        elif isinstance(screen, ExecutionScreen):
            screen.pause_requested.connect(self._on_pause_sync)
            screen.cancel_requested.connect(self._on_cancel_worker)
        elif isinstance(screen, SummaryScreen):
            screen.retry_requested.connect(self._on_retry_errors)
            screen.new_sync_requested.connect(self._on_new_sync)
            screen.export_analysis_requested.connect(self._on_export_analysis)
            screen.export_log_requested.connect(self._on_export_log)
            screen.save_snapshot_requested.connect(self._on_save_snapshot)
        elif name == 'snapshots':
            screen.back_requested.connect(self.show_setup)
            screen.snapshot_requested.connect(self._on_take_snapshot)

    # ── Screen navigation ──────────────────────────────────────────────

    def show_setup(self) -> None:
        screen = self._ensure_screen('setup')
        if screen:
            self._stack.setCurrentWidget(screen)

    def show_analysis(self) -> None:
        screen = self._ensure_screen('analysis')
        if screen:
            self._stack.setCurrentWidget(screen)

    def show_review(self) -> None:
        screen = self._ensure_screen('review')
        if screen:
            self._stack.setCurrentWidget(screen)

    def show_execution(self) -> None:
        screen = self._ensure_screen('execution')
        if screen:
            self._stack.setCurrentWidget(screen)

    def show_summary(self) -> None:
        screen = self._ensure_screen('summary')
        if screen:
            self._stack.setCurrentWidget(screen)

    def show_snapshots(self) -> None:
        screen = self._ensure_screen('snapshots')
        if screen:
            screen._refresh()
            self._stack.setCurrentWidget(screen)

    # ── Header ─────────────────────────────────────────────────────────

    def _create_header(self) -> QFrame:
        card = QFrame()
        card.setObjectName("headerCard")
        card.setStyleSheet(DesignSystem.get_header_style())
        card.setFixedHeight(56)

        layout = QHBoxLayout(card)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(DesignSystem.SPACE_16, 0, DesignSystem.SPACE_16, 0)

        icon_container = QFrame()
        icon_container.setFixedSize(48, 48)
        icon_container.setStyleSheet(DesignSystem.get_header_icon_container_style())
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon = QLabel()
        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            app_icon.setPixmap(pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_layout.addWidget(app_icon)
        layout.addWidget(icon_container)

        title = QLabel(Config.APP_NAME)
        title.setStyleSheet(DesignSystem.get_header_title_style())
        layout.addWidget(title)

        brand = QLabel(tr("header.by_safetoolhub"))
        brand.setStyleSheet(DesignSystem.get_header_brand_label_style())
        layout.addWidget(brand)

        layout.addStretch()

        btn_snapshots = QToolButton()
        btn_snapshots.setAutoRaise(True)
        btn_snapshots.setToolTip(tr("header.snapshots"))
        icon_manager.set_button_icon(btn_snapshots, "database", color=DesignSystem.COLOR_TEXT_SECONDARY, size=20)
        btn_snapshots.setStyleSheet(DesignSystem.get_icon_button_style())
        btn_snapshots.clicked.connect(self.show_snapshots)
        layout.addWidget(btn_snapshots)

        btn_settings = QToolButton()
        btn_settings.setAutoRaise(True)
        btn_settings.setToolTip(tr("header.settings"))
        icon_manager.set_button_icon(btn_settings, "cog", color=DesignSystem.COLOR_TEXT_SECONDARY, size=20)
        btn_settings.setStyleSheet(DesignSystem.get_icon_button_style())
        btn_settings.clicked.connect(self._show_settings)
        layout.addWidget(btn_settings)

        btn_about = QToolButton()
        btn_about.setAutoRaise(True)
        btn_about.setToolTip(tr("header.about"))
        icon_manager.set_button_icon(btn_about, "information-outline", color=DesignSystem.COLOR_TEXT_SECONDARY, size=20)
        btn_about.setStyleSheet(DesignSystem.get_icon_button_style())
        btn_about.clicked.connect(self._show_about)
        layout.addWidget(btn_about)

        return card

    # ── Dialogs ──────────────────────────────────────────────────────────

    def _show_settings(self) -> None:
        from sync_app.dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(settings_manager, parent=self)
        if dialog.exec():
            self._logger.info("Settings updated")
        if self._setup_screen:
            self._setup_screen.refresh_history()

    def _show_about(self) -> None:
        from sync_app.dialogs.about_dialog import AboutDialog
        dialog = AboutDialog(parent=self)
        dialog.exec()

    def _check_resume(self) -> None:
        try:
            manager = SyncStateManager()
            if manager.has_incomplete_sync():
                state = manager.load_state()
                if state:
                    from sync_app.dialogs.resume_dialog import ResumeDialog
                    completed = manager.get_completed_count()
                    total = state.get("total_ops", 0)
                    dest = state.get("dest", "")
                    dialog = ResumeDialog(completed_ops=completed, pending_ops=total - completed, destination=dest, parent=self)
                    dialog.exec()
                    if dialog.should_resume:
                        self._logger.info("Resuming previous sync")
                    else:
                        manager.clear_state()
                        self._logger.info("Discarded previous sync state")
        except Exception as e:
            self._logger.warning(f"Could not check resume state: {e}")

    # ── Worker management ────────────────────────────────────────────────

    def _cancel_active_worker(self) -> None:
        if self._active_worker is not None:
            self._active_worker.request_cancel()
            self._active_worker.wait(3000)
            self._active_worker = None

    def _start_resource_monitor(self, source_path: str = "", dest_path: str = "") -> None:
        self._stop_resource_monitor()
        self._resource_monitor = ResourceMonitorWorker(source_path=source_path, dest_path=dest_path)
        execution_screen = self._execution_screen
        if execution_screen:
            self._resource_monitor.resource_update.connect(execution_screen.set_resources)
        self._resource_monitor.start()

    def _stop_resource_monitor(self) -> None:
        if self._resource_monitor is not None:
            self._resource_monitor.request_cancel()
            self._resource_monitor.wait(2000)
            self._resource_monitor = None

    # ── Analysis pipeline ──────────────────────────────────────────────

    def _on_analyze(self) -> None:
        setup = self._ensure_screen('setup')
        if not setup:
            return

        source_path = setup.get_source_path()
        dest_path = setup.get_dest_path()
        if not source_path or not dest_path:
            self._logger.warning("Analyze requested without source/dest paths")
            return

        self._current_source = source_path
        self._current_dest = dest_path

        from services.exclusion_engine import get_preset_patterns
        presets = setup.get_active_exclusion_presets()
        exclusions = get_preset_patterns(presets) + setup.get_custom_exclusions()
        self._exclusions = exclusions

        self._logger.info(f"Starting scan: source={source_path}, dest={dest_path}")

        analysis = self._ensure_screen('analysis')
        if analysis:
            analysis.reset()

        self.show_analysis()

        self._source_worker = ScanWorker(
            root=Path(source_path),
            exclusions=exclusions,
        )
        self._source_worker.progress.connect(self._on_source_scan_progress)
        self._source_worker.finished.connect(self._on_source_scan_finished)
        self._source_worker.error.connect(self._on_scan_error)

        self._active_worker = self._source_worker
        self._source_worker.start()

    def _on_source_scan_progress(self, percent: int, message: str) -> None:
        analysis = self._analysis_screen
        if analysis:
            analysis.set_source_progress(percent, message)

    def _on_source_scan_finished(self, result: object) -> None:
        from services.models import ScanResult
        if not isinstance(result, ScanResult):
            self._logger.error("Source scan returned unexpected result type")
            return

        self._source_entries = result.entries
        self._logger.info(f"Source scan complete: {result.total_files} files, {format_size(result.total_size)}")

        analysis = self._analysis_screen
        if analysis:
            analysis.set_source_progress(100, tr("analysis.source_scan_complete"))
            analysis.set_metrics(result.total_files, result.total_size)

        self._dest_worker = ScanWorker(
            root=Path(self._current_dest),
            exclusions=self._exclusions,
        )
        self._dest_worker.progress.connect(self._on_dest_scan_progress)
        self._dest_worker.finished.connect(self._on_dest_scan_finished)
        self._dest_worker.error.connect(self._on_scan_error)

        self._active_worker = self._dest_worker
        self._dest_worker.start()

    def _on_dest_scan_progress(self, percent: int, message: str) -> None:
        analysis = self._analysis_screen
        if analysis:
            analysis.set_dest_progress(percent, message)

    def _on_dest_scan_finished(self, result: object) -> None:
        from services.models import ScanResult
        if not isinstance(result, ScanResult):
            self._logger.error("Dest scan returned unexpected result type")
            return

        self._dest_entries = result.entries
        self._logger.info(f"Dest scan complete: {result.total_files} files, {format_size(result.total_size)}")

        analysis = self._analysis_screen
        if analysis:
            analysis.set_dest_progress(100, tr("analysis.dest_scan_complete"))

        self._start_comparison()

    def _on_scan_error(self, error_msg: str) -> None:
        self._logger.error(f"Scan error: {error_msg}")
        self._active_worker = None

    def _start_comparison(self) -> None:
        setup = self._ensure_screen('setup')
        if not setup:
            return

        if setup.get_precompute_hashes():
            self._start_precompute_hashes()
            return

        self._launch_compare_worker()

    def _start_precompute_hashes(self) -> None:
        paths_to_hash: list[Path] = []
        path_to_entries: dict[str, list] = {}

        src_root = Path(self._current_source) if self._current_source else None
        dst_root = Path(self._current_dest) if self._current_dest else None

        if src_root:
            for entry in self._source_entries:
                if entry.is_dir or entry.hash_sha256:
                    continue
                p = src_root / entry.rel_path
                key = str(p)
                paths_to_hash.append(p)
                path_to_entries.setdefault(key, []).append(entry)

        if dst_root:
            for entry in self._dest_entries:
                if entry.is_dir or entry.hash_sha256:
                    continue
                p = dst_root / entry.rel_path
                key = str(p)
                paths_to_hash.append(p)
                path_to_entries.setdefault(key, []).append(entry)

        if not paths_to_hash:
            self._launch_compare_worker()
            return

        self._logger.info(f"Pre-computing hashes for {len(paths_to_hash)} files before comparison")
        self._hash_path_to_entries = path_to_entries

        self._hash_worker = HashWorker(paths_to_hash, parent=self)
        self._hash_worker.progress.connect(self._on_precompute_hash_progress)
        self._hash_worker.finished.connect(self._on_precompute_hash_finished)
        self._hash_worker.error.connect(self._on_compare_error)

        self._active_worker = self._hash_worker
        self._hash_worker.start()

    def _on_precompute_hash_progress(self, percent: int, message: str) -> None:
        analysis = self._analysis_screen
        if analysis:
            analysis.set_dest_progress(percent, tr("analysis.hashing_progress", percent=percent))

    def _on_precompute_hash_finished(self, result: object) -> None:
        if not isinstance(result, dict):
            self._logger.error("Hash worker returned unexpected result type")
            return

        for path_str, digest in result.items():
            entries = self._hash_path_to_entries.get(path_str, [])
            for entry in entries:
                entry.hash_sha256 = digest

        self._logger.info(f"Pre-compute hashes complete: {len(result)} hashes assigned")
        self._hash_path_to_entries = {}
        self._launch_compare_worker()

    def _launch_compare_worker(self) -> None:
        setup = self._ensure_screen('setup')
        if not setup:
            return

        compare_mode = setup.get_compare_mode()
        conflict_policy = setup.get_conflict_policy()
        conflict_action = setup.get_conflict_action()
        direction = setup.get_direction()
        dest_only_default = setup.get_dest_only_action()

        self._compare_worker = CompareWorker(
            source=self._source_entries,
            dest=self._dest_entries,
            mode=compare_mode,
            policy=conflict_policy,
            dest_only_default=dest_only_default,
            direction=direction,
            conflict_action=conflict_action,
        )
        self._compare_worker.progress.connect(self._on_compare_progress)
        self._compare_worker.finished.connect(self._on_compare_finished)
        self._compare_worker.error.connect(self._on_compare_error)

        self._active_worker = self._compare_worker
        self._compare_worker.start()

    def _on_compare_progress(self, percent: int, message: str) -> None:
        analysis = self._analysis_screen
        if analysis:
            analysis.set_dest_progress(percent, message)

    def _on_compare_finished(self, result: object) -> None:
        from services.models import ComparisonEntry
        if not isinstance(result, list):
            self._logger.error("Compare returned unexpected result type")
            return

        self._comparison_entries = result
        self._logger.info(f"Comparison complete: {len(result)} entries")

        rename_count = sum(1 for e in result if e.diff_type.value == "renamed")
        analysis = self._analysis_screen
        if analysis:
            analysis.set_renames_detected(rename_count)

        self._active_worker = None

        review = self._ensure_screen('review')
        if review:
            review.set_base_paths(self._current_source, self._current_dest)
            review.set_entries(result)
        self.show_review()

    def _on_compare_error(self, error_msg: str) -> None:
        self._logger.error(f"Compare error: {error_msg}")
        self._active_worker = None

    # ── Remaining slots ──────────────────────────────────────────────────

    def _on_cancel_worker(self) -> None:
        self._cancel_active_worker()
        self.show_setup()

    def _on_review_sync(self) -> None:
        self._logger.info("Sync requested from review — computing plan + space")
        if not self._comparison_entries:
            return
        from services.planner import build_plan
        from services.space_calculator import (
            calculate_required_space_per_side,
            check_destination_space,
        )

        setup = self._ensure_screen('setup')
        use_trash = setup.get_use_trash() if setup else True
        direction = setup.get_direction() if setup else SyncDirection.UNIDIRECTIONAL

        plan = build_plan(self._comparison_entries, use_trash=use_trash)
        self._sync_plan = plan

        dest_req, src_req = calculate_required_space_per_side(plan)
        dest_space = check_destination_space(Path(self._current_dest), dest_req)
        source_space = check_destination_space(Path(self._current_source), src_req)

        pending_conflicts = sum(
            1 for e in self._comparison_entries
            if e.diff_type.value == "conflict" and e.action == SyncAction.MARK_REVIEW
        )

        review = self._ensure_screen('review')
        if review:
            review.show_plan_panel(plan, dest_space, source_space, pending_conflicts, direction)

    def _on_resolve_conflicts(self) -> None:
        self._logger.info("Manual review requested")
        conflicts = [
            e for e in self._comparison_entries
            if e.action == SyncAction.MARK_REVIEW
        ]
        if conflicts:
            setup = self._ensure_screen('setup')
            direction = setup.get_direction() if setup else SyncDirection.UNIDIRECTIONAL
            assistant = self._ensure_screen('conflict')
            if assistant:
                assistant.set_conflicts(
                    conflicts,
                    direction=direction,
                    source_root=Path(self._current_source) if self._current_source else None,
                    dest_root=Path(self._current_dest) if self._current_dest else None,
                )
                self._stack.setCurrentWidget(assistant)

    def _on_resolve_conflicts_back(self) -> None:
        self._logger.info("Back from manual review assistant — returning to review")
        review = self._ensure_screen('review')
        if review:
            review.set_entries(self._comparison_entries)
        self.show_review()

    def _on_conflicts_resolved(self) -> None:
        self._logger.info("Manual review completed — returning to review")
        review = self._ensure_screen('review')
        if review:
            review.set_entries(self._comparison_entries)
        self.show_review()

    def _on_execute(self) -> None:
        self._logger.info("Execute requested")
        if not self._sync_plan or not self._current_source or not self._current_dest:
            return
        setup = self._ensure_screen('setup')
        verify_mode_str = "FULL"
        use_trash = True
        if setup:
            verify_mode_str = setup.get_verify_mode().value
            use_trash = setup.get_use_trash()

        execution = self._ensure_screen('execution')
        if execution:
            execution.reset()
        self.show_execution()
        self._start_resource_monitor(self._current_source, self._current_dest)

        worker = SyncWorker(
            plan=self._sync_plan,
            source_root=Path(self._current_source),
            dest_root=Path(self._current_dest),
            verify_mode=verify_mode_str,
            use_trash=use_trash,
        )
        worker.progress.connect(self._on_sync_progress)
        worker.file_completed.connect(self._on_file_completed)
        worker.file_verified.connect(self._on_file_verified)
        worker.finished.connect(self._on_sync_finished)
        worker.error.connect(self._on_sync_error)
        self._active_worker = worker
        self._sync_completed_count = 0
        self._sync_verified_count = 0
        self._sync_error_count = 0
        self._sync_skipped_count = 0
        self._sync_failed_rel_paths: list[str] = []
        worker.start()

    def _on_sync_progress(self, percent: int, message: str) -> None:
        execution = self._execution_screen
        if execution:
            execution.set_progress(percent, message)

    def _on_file_completed(self, rel_path: str, success: bool) -> None:
        execution = self._execution_screen
        if execution:
            if success:
                self._sync_completed_count += 1
            else:
                self._sync_error_count += 1
                self._sync_failed_rel_paths.append(rel_path)
            status = "OK" if success else "FAIL"
            execution.append_log(f"[{status}] {rel_path}")
            execution.set_counters(
                self._sync_completed_count,
                self._sync_verified_count,
                self._sync_error_count,
                self._sync_skipped_count,
            )

    def _on_file_verified(self, rel_path: str, verified: bool) -> None:
        execution = self._execution_screen
        if execution:
            if verified:
                self._sync_verified_count += 1
            else:
                self._sync_error_count += 1
            status = "VERIFIED" if verified else "VERIFY FAILED"
            execution.append_log(f"  [{status}] {rel_path}")
            execution.set_counters(
                self._sync_completed_count,
                self._sync_verified_count,
                self._sync_error_count,
                self._sync_skipped_count,
            )

    def _on_sync_finished(self, result: object) -> None:
        self._stop_resource_monitor()
        if not isinstance(result, SyncReport):
            self._logger.error("Sync finished with unexpected result type")
            return
        self._logger.info(f"Sync complete: {result.copied} copied, {result.errors} errors")
        self._last_sync_report = result
        summary = self._ensure_screen('summary')
        if summary:
            summary.set_dry_run_mode(False)
            summary.set_report(result)
        self.show_summary()

    def _on_sync_error(self, error_msg: str) -> None:
        self._stop_resource_monitor()
        self._logger.error(f"Sync error: {error_msg}")
        execution = self._execution_screen
        if execution:
            execution.append_log(f"[ERROR] {error_msg}")

    def _on_dry_run(self) -> None:
        self._logger.info("Dry run requested")
        if not self._sync_plan or not self._current_source or not self._current_dest:
            return
        setup = self._ensure_screen('setup')
        verify_mode_str = "FULL"
        use_trash = True
        if setup:
            verify_mode_str = setup.get_verify_mode().value
            use_trash = setup.get_use_trash()

        execution = self._ensure_screen('execution')
        if execution:
            execution.reset()
            execution.set_dry_run_mode(True)
        self.show_execution()

        worker = SyncWorker(
            plan=self._sync_plan,
            source_root=Path(self._current_source),
            dest_root=Path(self._current_dest),
            verify_mode=verify_mode_str,
            use_trash=use_trash,
            dry_run=True,
        )
        worker.progress.connect(self._on_sync_progress)
        worker.file_completed.connect(self._on_file_completed)
        worker.file_verified.connect(self._on_file_verified)
        worker.finished.connect(self._on_sync_finished_dry_run)
        worker.error.connect(self._on_sync_error)
        self._active_worker = worker
        self._sync_completed_count = 0
        self._sync_verified_count = 0
        self._sync_error_count = 0
        self._sync_skipped_count = 0
        self._sync_failed_rel_paths: list[str] = []
        worker.start()

    def _on_sync_finished_dry_run(self, result: object) -> None:
        if not isinstance(result, SyncReport):
            self._logger.error("Dry run finished with unexpected result type")
            return
        self._logger.info(f"Dry run complete: {result.copied} would copy, {result.deleted} would delete")
        self._last_sync_report = result
        summary = self._ensure_screen('summary')
        if summary:
            summary.set_dry_run_mode(True)
            summary.set_report(result)
        self.show_summary()

    def _on_pause_sync(self) -> None:
        self._logger.info("Pause/resume requested")
        if self._active_worker and isinstance(self._active_worker, SyncWorker):
            if self._active_worker.is_paused:
                self._active_worker.request_resume()
                self._logger.info("Sync resumed")
            else:
                self._active_worker.request_pause()
                self._logger.info("Sync paused")

    def _on_retry_errors(self) -> None:
        self._logger.info("Retry errors requested")
        if not self._sync_plan or not self._current_source or not self._current_dest:
            self.show_setup()
            return
        if not hasattr(self, '_sync_failed_rel_paths') or not self._sync_failed_rel_paths:
            self.show_setup()
            return

        failed_set = set(self._sync_failed_rel_paths)
        retry_entries = [e for e in self._sync_plan.entries if e.rel_path in failed_set]
        if not retry_entries:
            self.show_setup()
            return

        from services.models import SyncPlan, SyncAction
        total_copy = sum(
            (e.source.size if e.source else 0)
            for e in retry_entries
            if e.action in (SyncAction.COPY_TO_DEST, SyncAction.OVERWRITE_DEST)
        )
        retry_plan = SyncPlan(
            entries=retry_entries,
            total_copy_bytes=total_copy,
            total_delete_count=sum(1 for e in retry_entries if e.action == SyncAction.DELETE_FROM_DEST),
            total_overwrite_count=sum(1 for e in retry_entries if e.action in (SyncAction.OVERWRITE_DEST, SyncAction.OVERWRITE_SOURCE)),
            total_rename_count=sum(1 for e in retry_entries if e.action == SyncAction.RENAME_IN_DEST),
        )
        self._sync_plan = retry_plan
        self._logger.info(f"Retrying {len(retry_entries)} failed entries")
        self._on_execute()

    def _on_new_sync(self) -> None:
        self._cancel_active_worker()
        self._stop_resource_monitor()
        self.show_setup()

    def _on_export_analysis(self) -> None:
        self._logger.info("Export analysis requested")
        if self._comparison_entries:
            from services.analysis_export import export_analysis
            from pathlib import Path as P
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, tr("analysis.export_title"), "", "JSON (*.json)")
            if path:
                export_analysis(self._comparison_entries, P(path))
                self._logger.info(f"Analysis exported to {path}")

    def _on_export_log(self) -> None:
        self._logger.info("Export log requested")
        if not self._last_sync_report:
            return
        from datetime import datetime
        from services.analysis_export import export_sync_log
        from pathlib import Path as P
        from PyQt6.QtWidgets import QFileDialog
        default_name = f"safetool_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("summary.export_log"), default_name, "Text (*.txt)"
        )
        if path:
            export_sync_log(
                self._last_sync_report,
                self._comparison_entries,
                P(path),
                source=self._current_source,
                dest=self._current_dest,
            )
            self._logger.info(f"Sync log exported to {path}")

    def _on_save_snapshot(self) -> None:
        self._logger.info("Save snapshot requested")
        if self._source_entries:
            from services.snapshot_manager import SnapshotManager
            mgr = SnapshotManager()
            mgr.save_snapshot(self._current_source, "Source", self._source_entries)
            self._logger.info(f"Snapshot saved for {self._current_source}")

    def _on_take_snapshot(self, mount_point: str, label: str) -> None:
        self._logger.info(f"Snapshot requested for {mount_point} ({label})")
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        safe_label = label.replace("/", "_").replace("\\", "_").replace(":", "_").strip("_") or "disco"
        default_name = f"{safe_label}_snapshot.db"
        default_dir = str(Config.SNAPSHOTS_DIR)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("setup.snapshot_save_dialog_title"),
            str(Path(default_dir) / default_name),
            tr("setup.snapshot_save_dialog_filter"),
        )
        if not save_path:
            return

        save_path_obj = Path(save_path)
        if save_path_obj.suffix.lower() != ".db":
            save_path_obj = save_path_obj.with_suffix(".db")

        save_path_obj.parent.mkdir(parents=True, exist_ok=True)

        self._logger.info(f"Snapshot will be saved to: {save_path_obj}")

        worker = ScanWorker(root=Path(mount_point), exclusions=[])

        def _on_done(result: object) -> None:
            from services.models import ScanResult
            if isinstance(result, ScanResult):
                from services.snapshot_manager import SnapshotManager
                mgr = SnapshotManager(snapshots_dir=save_path_obj.parent)
                disk_id = save_path_obj.stem
                mgr.save_snapshot(disk_id, label, result.entries)
                self._logger.info(f"Snapshot saved: {save_path_obj} — {result.total_files} files")
                QMessageBox.information(
                    self,
                    tr("setup.snapshot_save_dialog_title"),
                    tr("setup.snapshot_saved_ok", path=str(save_path_obj)),
                )

        def _on_err(msg: str) -> None:
            self._logger.error(f"Snapshot scan error: {msg}")
            QMessageBox.warning(self, tr("common.error"), msg)

        worker.finished.connect(_on_done)
        worker.error.connect(_on_err)
        worker.start()
        self._active_worker = worker

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _on_save_session(self) -> None:
        if not self._comparison_entries:
            return
        from datetime import datetime
        from services.session_manager import save_session
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        sessions_dir = Path.home() / ".safetool_sync" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        default_name = f"review_session_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

        setup = self._ensure_screen('setup')
        direction = setup.get_direction() if setup else SyncDirection.UNIDIRECTIONAL

        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("review.save_session"),
            str(sessions_dir / default_name),
            tr("review.session_save_filter"),
        )
        if not path:
            return

        try:
            save_session(
                Path(path),
                self._current_source,
                self._current_dest,
                direction,
                self._comparison_entries,
            )
            QMessageBox.information(
                self,
                tr("review.save_session"),
                tr("review.session_saved_ok", path=path),
            )
            self._logger.info(f"Session saved to {path}")
        except Exception as e:
            self._logger.error(f"Save session failed: {e}")
            QMessageBox.warning(
                self,
                tr("review.save_session"),
                tr("review.session_save_failed", error=str(e)),
            )

    def _on_load_session(self) -> None:
        from services.session_manager import (
            load_session,
            compute_analysis_hash,
            SessionVersionError,
        )
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        sessions_dir = Path.home() / ".safetool_sync" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("review.load_session"),
            str(sessions_dir),
            tr("review.session_save_filter"),
        )
        if not path:
            return

        try:
            session = load_session(Path(path))
        except SessionVersionError as e:
            QMessageBox.warning(
                self,
                tr("review.load_session"),
                tr("review.session_unsupported_version", version=str(e)),
            )
            return
        except Exception as e:
            self._logger.error(f"Load session failed: {e}")
            QMessageBox.warning(
                self,
                tr("review.load_session"),
                tr("review.session_load_failed", error=str(e)),
            )
            return

        if (
            session.source_path != self._current_source
            or session.dest_path != self._current_dest
        ):
            QMessageBox.warning(
                self,
                tr("review.load_session"),
                tr(
                    "review.session_paths_mismatch",
                    saved_source=session.source_path,
                    saved_dest=session.dest_path,
                    current_source=self._current_source,
                    current_dest=self._current_dest,
                ),
            )
            return

        drift_note = ""
        review = self._ensure_screen('review')
        if review:
            if compute_analysis_hash(self._comparison_entries) != session.analysis_hash:
                drift_note = "\n\n" + tr("review.session_drifted")

        body = tr(
            "review.session_confirm_apply",
            saved_at=session.saved_at,
            source=session.source_path,
            dest=session.dest_path,
            count=len(session.actions),
            drift_note=drift_note,
        )
        btn = QMessageBox.question(
            self,
            tr("review.session_confirm_apply_title"),
            body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if btn != QMessageBox.StandardButton.Yes:
            return

        if review:
            result = review.apply_loaded_session_actions(session)
            msg = tr(
                "review.session_loaded",
                applied=result.applied,
                skipped=result.skipped_invalid,
                stale=result.stale,
            )
            if result.analysis_drifted:
                msg += "\n" + tr("review.session_drifted")
            QMessageBox.information(self, tr("review.load_session"), msg)
            self._logger.info(
                f"Session loaded from {path}: applied={result.applied}, "
                f"skipped={result.skipped_invalid}, stale={result.stale}, "
                f"drifted={result.analysis_drifted}"
            )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not hasattr(self, '_resume_checked'):
            self._resume_checked = True
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._check_resume)

    def closeEvent(self, event) -> None:
        self._cancel_active_worker()
        self._stop_resource_monitor()
        self._logger.info(f"{Config.APP_NAME} closing")
        super().closeEvent(event)