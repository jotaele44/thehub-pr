"""Renders a ``CheckReport`` for the CLI table and the desktop GUI's diagnostics list."""

from __future__ import annotations

from .types import CheckReport

# Maps the doctor's 5-value CheckStatus onto the 2-value vocabulary
# `prii_desktop.setup_center.diagnostics()` already emits ("pass"/"fail"),
# extended with "warn"/"info". An unrecognized status in the frontend's CSS
# already falls back to a neutral gray dot (never green) -- see
# `render_setup_html()` -- so a value missing from this map degrades safely.
_STATUS_TO_GUI = {
    "PASS": "pass",
    "FAIL": "fail",
    "WARN": "warn",
    "SKIP": "info",
    "INFO": "info",
}


def print_table(report: CheckReport) -> None:
    rows = report.as_rows()
    if not rows:
        print("No doctor checks declared (.federation/doctor-checks.json not found).")
        return
    width_id = max(len(r[0]) for r in rows)
    width_class = max(len(r[1]) for r in rows)
    width_status = max(len(r[2]) for r in rows)
    print(f"\n{'CHECK'.ljust(width_id)}  {'CLASS'.ljust(width_class)}  {'STATUS'.ljust(width_status)}  DETAIL")
    print(f"{'-' * width_id}  {'-' * width_class}  {'-' * width_status}  ------")
    for check_id, cls, status, detail in rows:
        print(f"{check_id.ljust(width_id)}  {cls.ljust(width_class)}  {status.ljust(width_status)}  {detail}")
    print()
    if report.all_blocking_passed:
        print("OK — no blocking doctor failures.")
    else:
        blocking = [r for r in report.results if r.is_blocking_failure]
        print(f"FAIL — {len(blocking)} blocking doctor check(s) failed.")


def to_gui_dicts(report: CheckReport) -> list[dict[str, str]]:
    """Adapt a CheckReport to the wire format ``setup_center.diagnostics()``
    already returns: ``{"label", "status", "detail"}``. Adds a ``class``
    field the frontend may use for tooltip text.
    """
    out: list[dict[str, str]] = []
    for r in report.results:
        detail = r.detail
        if r.operator_action:
            detail = f"{detail} Operator action: {r.operator_action}".strip()
        out.append(
            {
                "label": r.check_id,
                "status": _STATUS_TO_GUI.get(r.status, "info"),
                "detail": detail,
                "class": r.diagnosability_class.value,
            }
        )
    return out
