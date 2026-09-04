"""Screenshots the real running frontend with Playwright, driven directly (no MCP connected this
machine -- see handoff.md). This is T37's visual-iteration harness: every "before"/"after" claim
about the redesign is verified against an actual screenshot, not against what the CSS says it
should look like (D83->D95->D105 is three consecutive instances of first-principles visual
reasoning being wrong until someone looked at a real render).

Usage (with `python -m scripts.serve_fake` on :8000 and `npm run dev` on :5173 both running):
    python scripts/shoot_ui.py --out <dir>                    # all named scenarios, light, desktop
    python scripts/shoot_ui.py --out <dir> --dark              # same, OS dark-mode -- must still be light
    python scripts/shoot_ui.py --out <dir> --mobile            # 390px viewport
    python scripts/shoot_ui.py --out <dir> --url https://nomu.store --name nomu
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

STATIC_ROUTES = {
    "landing": "/",
    "dashboard": "/jobs",
    "library": "/library",
    "not-found": "/this-route-does-not-exist",
}

SAMPLE_TOPIC = "teach me about SQL injection"


def _shoot(page, out: Path, name: str) -> None:
    page.wait_for_load_state("networkidle", timeout=15_000)
    page.screenshot(path=str(out / f"{name}.png"), full_page=True)
    print(f"  wrote {name}.png")


def _static_routes(page, base_url: str, out: Path) -> None:
    for name, route in STATIC_ROUTES.items():
        page.goto(f"{base_url}{route}")
        _shoot(page, out, name)


def _composing(page, base_url: str, out: Path) -> None:
    page.goto(base_url)
    page.wait_for_load_state("networkidle", timeout=15_000)
    page.get_by_role("textbox").fill(SAMPLE_TOPIC)
    _shoot(page, out, "composing")


def _submit_and_track(page, base_url: str, out: Path) -> None:
    """Submits a real job against `serve_fake` and screenshots queued -> running -> terminal.
    Set FAKE_STAGE_DELAY_MS on the serve_fake process (e.g. 1500) or queued/running will be
    indistinguishable -- a fake job otherwise completes in well under a second."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle", timeout=15_000)
    page.get_by_role("textbox").fill(SAMPLE_TOPIC)
    page.get_by_role("button", name="Make the video").click()
    page.wait_for_url("**/jobs/*", timeout=15_000)
    _shoot(page, out, "queued")

    page.wait_for_timeout(2_000)
    _shoot(page, out, "running")

    terminal = page.get_by_text("Succeeded").or_(page.get_by_text("Failed"))
    terminal.first.wait_for(timeout=120_000)
    status = "succeeded" if page.get_by_text("Succeeded").count() else "failed"
    _shoot(page, out, status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--url", help="one-off URL to shoot instead of the named scenarios")
    parser.add_argument("--name", default="page", help="filename stem for --url")
    parser.add_argument("--dark", action="store_true", help="force OS color-scheme: dark")
    parser.add_argument("--mobile", action="store_true", help="390px viewport instead of 1440px")
    parser.add_argument(
        "--skip-submit", action="store_true", help="skip the job-submission scenario"
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    viewport = MOBILE if args.mobile else DESKTOP
    color_scheme = "dark" if args.dark else "light"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(viewport=viewport, color_scheme=color_scheme)
            page = context.new_page()

            if args.url:
                page.goto(args.url)
                _shoot(page, args.out, args.name)
            else:
                _static_routes(page, args.base_url, args.out)
                _composing(page, args.base_url, args.out)
                if not args.skip_submit:
                    _submit_and_track(page, args.base_url, args.out)
        finally:
            browser.close()

    print(f"done -> {args.out}")


if __name__ == "__main__":
    main()
