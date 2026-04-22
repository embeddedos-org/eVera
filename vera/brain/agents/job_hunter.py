"""Job Hunter Agent — autonomously searches for and applies to jobs.

Uses DuckDuckGo + Playwright browser automation to find job listings,
evaluate fit via LLM scoring, generate cover letters, and fill/submit
application forms. All activity is logged to data/job_applications.json.

Install: pip install playwright && python -m playwright install chromium
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
PROFILE_PATH = DATA_DIR / "job_profile" / "profile.json"
APPLICATIONS_PATH = DATA_DIR / "job_applications.json"


def _ensure_dirs() -> None:
    (DATA_DIR / "job_profile").mkdir(parents=True, exist_ok=True)


def _load_profile() -> dict[str, Any]:
    _ensure_dirs()
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_profile(profile: dict[str, Any]) -> None:
    _ensure_dirs()
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, default=str))


def _load_applications() -> list[dict[str, Any]]:
    if APPLICATIONS_PATH.exists():
        try:
            return json.loads(APPLICATIONS_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _save_applications(apps: list[dict[str, Any]]) -> None:
    _ensure_dirs()
    APPLICATIONS_PATH.write_text(json.dumps(apps, indent=2, default=str))


def _today_application_count() -> int:
    today = date.today().isoformat()
    apps = _load_applications()
    return sum(1 for a in apps if a.get("applied_at", "").startswith(today) and a.get("status") == "applied")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class SearchJobsTool(Tool):
    """Search for jobs using DuckDuckGo + direct site queries."""

    def __init__(self) -> None:
        super().__init__(
            name="search_jobs",
            description="Search for job postings online via DuckDuckGo",
            parameters={
                "query": {"type": "str", "description": "Job search query (e.g. 'Software Engineer Remote')"},
                "num_results": {"type": "int", "description": "Number of results (default 10)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        num = kwargs.get("num_results", 10)
        if not query:
            from config import settings
            titles = settings.job_hunter.target_titles
            locations = settings.job_hunter.target_locations
            if titles:
                query = " OR ".join(f'"{t}"' for t in titles)
                if locations:
                    query += " " + " OR ".join(locations)
            else:
                return {"status": "error", "message": "No query provided and no target_titles configured"}

        search_query = f"{query} site:linkedin.com/jobs OR site:indeed.com OR site:greenhouse.io OR site:lever.co"

        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=num))
            jobs = [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in results
            ]
            return {"status": "success", "query": query, "jobs": jobs, "count": len(jobs)}
        except Exception as e:
            try:
                import httpx
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"
                headers = {"User-Agent": "Mozilla/5.0 (compatible; Vera/1.0)"}
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, headers=headers, follow_redirects=True)

                import re
                links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', resp.text)
                snippets = re.findall(r'class="result__snippet"[^>]*>([^<]*)<', resp.text)
                jobs = []
                for i, (href, title) in enumerate(links[:num]):
                    snippet = snippets[i] if i < len(snippets) else ""
                    jobs.append({"title": title.strip(), "url": href.strip(), "snippet": snippet.strip()})
                return {"status": "success", "query": query, "jobs": jobs, "count": len(jobs), "method": "fallback"}
            except Exception as e2:
                return {"status": "error", "message": f"Search failed: {e2}"}


class BrowseJobBoardTool(Tool):
    """Navigate to a job board and extract listing cards via Playwright."""

    def __init__(self) -> None:
        super().__init__(
            name="browse_job_board",
            description="Navigate to a job board search page and extract job listing cards",
            parameters={
                "url": {"type": "str", "description": "Job board search URL"},
                "max_listings": {"type": "int", "description": "Max listings to extract (default 20)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        url = kwargs.get("url", "")
        max_listings = kwargs.get("max_listings", 20)
        if not url:
            return {"status": "error", "message": "No URL provided"}

        try:
            from vera.brain.agents.browser import _get_page, _save_cookies

            page = await _get_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            listings = await page.evaluate("""(max) => {
                const cards = document.querySelectorAll(
                    '[class*="job"], [class*="result"], [class*="posting"], [class*="card"], [class*="listing"]'
                );
                const results = [];
                for (const card of Array.from(cards).slice(0, max)) {
                    const linkEl = card.querySelector('a[href]');
                    const titleEl = card.querySelector('h2, h3, [class*="title"]');
                    const companyEl = card.querySelector('[class*="company"], [class*="employer"]');
                    const locationEl = card.querySelector('[class*="location"]');
                    if (titleEl) {
                        results.push({
                            title: titleEl.innerText.trim().substring(0, 120),
                            company: companyEl ? companyEl.innerText.trim().substring(0, 80) : '',
                            location: locationEl ? locationEl.innerText.trim().substring(0, 80) : '',
                            url: linkEl ? linkEl.href : '',
                        });
                    }
                }
                return results;
            }""", max_listings)

            await _save_cookies()
            return {"status": "success", "url": url, "listings": listings, "count": len(listings)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ReadJobPostingTool(Tool):
    """Extract full job description from a URL (httpx first, Playwright fallback)."""

    def __init__(self) -> None:
        super().__init__(
            name="read_job_posting",
            description="Extract the full job description text from a job posting URL",
            parameters={
                "url": {"type": "str", "description": "URL of the job posting"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        url = kwargs.get("url", "")
        if not url:
            return {"status": "error", "message": "No URL provided"}

        # Try httpx + BeautifulSoup first (faster)
        try:
            import httpx
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Vera/1.0)"}
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)

            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                text = soup.get_text(separator="\n", strip=True)[:5000]
                if len(text) > 500:
                    return {"status": "success", "url": url, "title": title, "description": text}
            except ImportError:
                import re
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text).strip()[:5000]
                if len(text) > 500:
                    return {"status": "success", "url": url, "title": "", "description": text}
        except Exception:
            pass

        # Fallback to Playwright for JS-rendered pages
        try:
            from vera.brain.agents.browser import _get_page, _save_cookies

            page = await _get_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            title = await page.title()
            text = await page.inner_text("body", timeout=10000)
            text = text.strip()[:5000]
            await _save_cookies()
            return {"status": "success", "url": url, "title": title, "description": text}
        except Exception as e:
            return {"status": "error", "message": f"Failed to read job posting: {e}"}


class EvaluateJobFitTool(Tool):
    """Score how well a job matches the user's profile via LLM."""

    def __init__(self) -> None:
        super().__init__(
            name="evaluate_job_fit",
            description="Use AI to score how well a job posting matches the user profile (0-1)",
            parameters={
                "job_description": {"type": "str", "description": "Full text of the job description"},
                "job_title": {"type": "str", "description": "Job title"},
                "company": {"type": "str", "description": "Company name"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        desc = kwargs.get("job_description", "")
        title = kwargs.get("job_title", "")
        company = kwargs.get("company", "")
        if not desc:
            return {"status": "error", "message": "No job description provided"}

        profile = _load_profile()
        if not profile:
            return {"status": "error", "message": "No job profile configured — use update_profile first"}

        from config import settings
        excluded = [c.lower() for c in settings.job_hunter.excluded_companies]
        if company.lower() in excluded:
            return {"status": "skipped", "score": 0, "reasoning": f"{company} is in excluded companies list", "recommendation": "skip"}

        prompt = (
            "You are a career matching expert. Score how well this job matches the candidate's profile.\n\n"
            f"JOB TITLE: {title}\nCOMPANY: {company}\n\nJOB DESCRIPTION:\n{desc[:3000]}\n\n"
            f"CANDIDATE PROFILE:\n{json.dumps(profile, indent=2, default=str)[:2000]}\n\n"
            "Respond with ONLY a JSON object (no markdown):\n"
            '{"score": 0.0-1.0, "reasoning": "brief explanation", "recommendation": "apply" or "skip"}'
        )

        try:
            from vera.providers.manager import ProviderManager
            provider = ProviderManager()
            result = await provider.complete(
                messages=[{"role": "user", "content": prompt}],
                tier=ModelTier.SPECIALIST,
                max_tokens=300,
                temperature=0.2,
            )
            parsed = json.loads(result.content.strip())
            return {
                "status": "success",
                "score": float(parsed.get("score", 0)),
                "reasoning": parsed.get("reasoning", ""),
                "recommendation": parsed.get("recommendation", "skip"),
            }
        except Exception as e:
            logger.warning("Job fit evaluation failed: %s", e)
            return {"status": "error", "message": str(e)}


class GenerateCoverLetterTool(Tool):
    """Generate a tailored cover letter using LLM."""

    def __init__(self) -> None:
        super().__init__(
            name="generate_cover_letter",
            description="Generate a tailored cover letter for a specific job posting",
            parameters={
                "job_title": {"type": "str", "description": "Job title"},
                "company": {"type": "str", "description": "Company name"},
                "job_description": {"type": "str", "description": "Job description text"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        title = kwargs.get("job_title", "")
        company = kwargs.get("company", "")
        desc = kwargs.get("job_description", "")

        profile = _load_profile()
        if not profile:
            return {"status": "error", "message": "No job profile — use update_profile first"}

        prompt = (
            "Write a concise, professional cover letter for this job application.\n"
            "Keep it under 300 words. Be specific about how the candidate's experience matches.\n\n"
            f"JOB TITLE: {title}\nCOMPANY: {company}\n\n"
            f"JOB DESCRIPTION:\n{desc[:2000]}\n\n"
            f"CANDIDATE PROFILE:\n{json.dumps(profile, indent=2, default=str)[:2000]}\n\n"
            "Write only the cover letter text, no commentary."
        )

        try:
            from vera.providers.manager import ProviderManager
            provider = ProviderManager()
            result = await provider.complete(
                messages=[{"role": "user", "content": prompt}],
                tier=ModelTier.SPECIALIST,
                max_tokens=600,
                temperature=0.7,
            )
            return {"status": "success", "cover_letter": result.content.strip()}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class FillApplicationTool(Tool):
    """Navigate to an application page and fill form fields using profile data."""

    def __init__(self) -> None:
        super().__init__(
            name="fill_application",
            description="Navigate to a job application page and auto-fill all form fields from your profile",
            parameters={
                "url": {"type": "str", "description": "Application page URL"},
                "cover_letter": {"type": "str", "description": "Cover letter text to include (optional)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        url = kwargs.get("url", "")
        cover_letter = kwargs.get("cover_letter", "")
        if not url:
            return {"status": "error", "message": "No application URL provided"}

        profile = _load_profile()
        if not profile:
            return {"status": "error", "message": "No job profile — use update_profile first"}

        personal = profile.get("personal", {})
        answers = profile.get("common_answers", {})

        try:
            from vera.brain.agents.browser import _get_page, _save_cookies

            page = await _get_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            filled_count = 0

            # Build mapping of field keywords to values
            field_map = {
                "name": personal.get("name", ""),
                "first": personal.get("name", "").split()[0] if personal.get("name") else "",
                "last": personal.get("name", "").split()[-1] if personal.get("name") else "",
                "email": personal.get("email", ""),
                "phone": personal.get("phone", ""),
                "location": personal.get("location", ""),
                "city": personal.get("location", ""),
                "linkedin": personal.get("linkedin_url", ""),
                "github": personal.get("github_url", ""),
                "portfolio": personal.get("portfolio_url", ""),
                "website": personal.get("portfolio_url", ""),
                "cover": cover_letter,
                "summary": profile.get("summary", ""),
                "salary": answers.get("desired_salary", ""),
                "experience": answers.get("years_of_experience", ""),
                "authorization": answers.get("work_authorization", ""),
                "sponsorship": answers.get("requires_sponsorship", ""),
                "relocate": answers.get("willing_to_relocate", ""),
            }

            # Get all visible form inputs
            inputs = await page.eval_on_selector_all(
                "input:not([type='hidden']):not([type='submit']):not([type='button']), textarea",
                """els => els.map(el => ({
                    tag: el.tagName,
                    type: el.type || 'text',
                    name: (el.name || '').toLowerCase(),
                    placeholder: (el.placeholder || '').toLowerCase(),
                    label: (el.ariaLabel || '').toLowerCase(),
                    id: (el.id || '').toLowerCase(),
                    selector: el.name ? 'input[name=\"' + el.name + '\"]'
                        : el.id ? '#' + el.id
                        : null,
                    visible: el.offsetParent !== null,
                }))""",
            )

            for inp in inputs:
                if not inp.get("visible") or not inp.get("selector"):
                    continue

                identifiers = f"{inp.get('name', '')} {inp.get('placeholder', '')} {inp.get('label', '')} {inp.get('id', '')}"

                for keyword, value in field_map.items():
                    if value and keyword in identifiers:
                        try:
                            await page.fill(inp["selector"], str(value), timeout=3000)
                            filled_count += 1
                        except Exception:
                            pass
                        break

            await _save_cookies()
            return {
                "status": "success",
                "url": url,
                "fields_filled": filled_count,
                "total_inputs": len(inputs),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class UploadResumeTool(Tool):
    """Upload resume PDF via file input on the application page."""

    def __init__(self) -> None:
        super().__init__(
            name="upload_resume",
            description="Upload resume PDF to a file input on the current application page",
            parameters={
                "resume_path": {"type": "str", "description": "Path to resume file (optional, uses config default)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings

        path = kwargs.get("resume_path", "") or settings.job_hunter.resume_path
        resume_file = Path(path)
        if not resume_file.exists():
            return {"status": "error", "message": f"Resume file not found: {path}"}

        try:
            from vera.brain.agents.browser import _get_page

            page = await _get_page()
            file_inputs = await page.query_selector_all('input[type="file"]')
            if not file_inputs:
                return {"status": "error", "message": "No file upload input found on page"}

            await file_inputs[0].set_input_files(str(resume_file.resolve()))
            return {"status": "success", "uploaded": str(resume_file)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SubmitApplicationTool(Tool):
    """Click the submit button on a filled application form."""

    def __init__(self) -> None:
        super().__init__(
            name="submit_application",
            description="Click the submit/apply button on the current application page",
            parameters={
                "job_title": {"type": "str", "description": "Job title for tracking"},
                "company": {"type": "str", "description": "Company name for tracking"},
                "job_url": {"type": "str", "description": "Original job posting URL"},
                "source": {"type": "str", "description": "Source (linkedin, indeed, etc.)"},
                "cover_letter": {"type": "str", "description": "Cover letter used (for logging)"},
                "match_score": {"type": "float", "description": "Fit score from evaluate_job_fit"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        title = kwargs.get("job_title", "Unknown")
        company = kwargs.get("company", "Unknown")
        job_url = kwargs.get("job_url", "")
        source = kwargs.get("source", "unknown")
        cover_letter = kwargs.get("cover_letter", "")
        score = kwargs.get("match_score", 0)

        try:
            from vera.brain.agents.browser import _get_page, _save_cookies

            page = await _get_page()

            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Apply")',
                'button:has-text("Send Application")',
                'button:has-text("Submit Application")',
            ]

            clicked = False
            for sel in submit_selectors:
                try:
                    await page.click(sel, timeout=3000)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                return {"status": "error", "message": "Could not find submit button"}

            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await _save_cookies()

            # Log application
            app_record = {
                "id": str(uuid.uuid4()),
                "title": title,
                "company": company,
                "url": job_url,
                "source": source,
                "status": "applied",
                "applied_at": datetime.now().isoformat(),
                "cover_letter": cover_letter[:500],
                "match_score": score,
                "error": None,
            }
            apps = _load_applications()
            apps.append(app_record)
            _save_applications(apps)

            return {"status": "success", "message": f"Application submitted to {company} for {title}!", "record": app_record}
        except Exception as e:
            # Log failed application
            app_record = {
                "id": str(uuid.uuid4()),
                "title": title,
                "company": company,
                "url": job_url,
                "source": source,
                "status": "failed",
                "applied_at": datetime.now().isoformat(),
                "cover_letter": cover_letter[:500],
                "match_score": score,
                "error": str(e),
            }
            apps = _load_applications()
            apps.append(app_record)
            _save_applications(apps)
            return {"status": "error", "message": f"Submit failed: {e}"}


class CheckApplicationStatusTool(Tool):
    """Review the tracking log of past applications."""

    def __init__(self) -> None:
        super().__init__(
            name="check_application_status",
            description="Show a summary of all past job applications and their status",
            parameters={
                "status_filter": {"type": "str", "description": "Filter by status: applied, skipped, failed, all (default: all)"},
                "limit": {"type": "int", "description": "Max entries to show (default 20)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        status_filter = kwargs.get("status_filter", "all")
        limit = kwargs.get("limit", 20)

        apps = _load_applications()
        if status_filter != "all":
            apps = [a for a in apps if a.get("status") == status_filter]

        total = len(apps)
        recent = apps[-limit:] if limit else apps

        summary = {
            "applied": sum(1 for a in _load_applications() if a.get("status") == "applied"),
            "skipped": sum(1 for a in _load_applications() if a.get("status") == "skipped"),
            "failed": sum(1 for a in _load_applications() if a.get("status") == "failed"),
        }

        return {
            "status": "success",
            "total": total,
            "summary": summary,
            "applications": [
                {k: v for k, v in a.items() if k != "cover_letter"}
                for a in recent
            ],
        }


class UpdateProfileTool(Tool):
    """Update the user's job application profile."""

    def __init__(self) -> None:
        super().__init__(
            name="update_profile",
            description="Update your job application profile (personal info, experience, skills, etc.)",
            parameters={
                "field": {"type": "str", "description": "Top-level field to update: personal, summary, experience, education, skills, certifications, common_answers"},
                "value": {"type": "str", "description": "JSON string of the new value for the field"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        field = kwargs.get("field", "")
        value_str = kwargs.get("value", "")
        if not field or not value_str:
            return {"status": "error", "message": "Both 'field' and 'value' are required"}

        profile = _load_profile()

        try:
            value = json.loads(value_str) if value_str.startswith(("{", "[", '"')) else value_str
        except json.JSONDecodeError:
            value = value_str

        if field in ("personal", "common_answers") and isinstance(value, dict):
            existing = profile.get(field, {})
            existing.update(value)
            profile[field] = existing
        else:
            profile[field] = value

        _save_profile(profile)
        return {"status": "success", "field": field, "message": f"Profile '{field}' updated"}


class SetPreferencesTool(Tool):
    """Update job search preferences at runtime."""

    def __init__(self) -> None:
        super().__init__(
            name="set_preferences",
            description="Update job search preferences (titles, locations, salary, exclusions)",
            parameters={
                "target_titles": {"type": "str", "description": "Comma-separated desired job titles"},
                "target_locations": {"type": "str", "description": "Comma-separated preferred locations"},
                "min_salary": {"type": "int", "description": "Minimum salary filter"},
                "excluded_companies": {"type": "str", "description": "Comma-separated companies to skip"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings

        updated = {}
        if titles := kwargs.get("target_titles"):
            settings.job_hunter.target_titles = [t.strip() for t in titles.split(",")]
            updated["target_titles"] = settings.job_hunter.target_titles
        if locations := kwargs.get("target_locations"):
            settings.job_hunter.target_locations = [l.strip() for l in locations.split(",")]
            updated["target_locations"] = settings.job_hunter.target_locations
        if salary := kwargs.get("min_salary"):
            settings.job_hunter.min_salary = int(salary)
            updated["min_salary"] = settings.job_hunter.min_salary
        if excluded := kwargs.get("excluded_companies"):
            settings.job_hunter.excluded_companies = [c.strip() for c in excluded.split(",")]
            updated["excluded_companies"] = settings.job_hunter.excluded_companies

        if not updated:
            return {"status": "error", "message": "No preferences provided to update"}

        return {"status": "success", "updated": updated}


class RunJobScanTool(Tool):
    """Execute a full scan: search → evaluate → apply cycle."""

    def __init__(self) -> None:
        super().__init__(
            name="run_job_scan",
            description="Run a full job scan cycle: search for new jobs, evaluate fit, and auto-apply to matches",
            parameters={
                "query": {"type": "str", "description": "Optional custom search query (uses config defaults if empty)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings

        query = kwargs.get("query", "")
        if not settings.job_hunter.target_titles and not query:
            return {"status": "error", "message": "No target titles or query configured — set preferences first"}

        daily_count = _today_application_count()
        max_daily = settings.job_hunter.max_daily_applications
        if daily_count >= max_daily:
            return {"status": "capped", "message": f"Daily cap reached ({daily_count}/{max_daily}). Try again tomorrow!"}

        remaining = max_daily - daily_count

        # Step 1: Search
        search = SearchJobsTool()
        search_result = await search.execute(query=query, num_results=20)
        if search_result.get("status") != "success":
            return {"status": "error", "message": "Job search failed", "detail": search_result}

        jobs = search_result.get("jobs", [])
        if not jobs:
            return {"status": "success", "message": "No new jobs found", "applied": 0, "skipped": 0, "failed": 0}

        # Filter already-applied URLs
        existing_urls = {a.get("url") for a in _load_applications()}
        new_jobs = [j for j in jobs if j.get("url") not in existing_urls]

        applied, skipped, failed = 0, 0, 0
        evaluate = EvaluateJobFitTool()
        cover_gen = GenerateCoverLetterTool()

        for job in new_jobs:
            if applied >= remaining:
                break

            url = job.get("url", "")
            title = job.get("title", "")

            # Step 2: Read full posting
            reader = ReadJobPostingTool()
            posting = await reader.execute(url=url)
            desc = posting.get("description", job.get("snippet", ""))

            # Step 3: Evaluate fit
            eval_result = await evaluate.execute(
                job_description=desc, job_title=title, company=job.get("company", ""),
            )
            score = eval_result.get("score", 0)
            recommendation = eval_result.get("recommendation", "skip")

            if recommendation == "skip" or score < settings.job_hunter.fit_threshold:
                # Log as skipped
                apps = _load_applications()
                apps.append({
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "company": job.get("company", ""),
                    "url": url,
                    "source": "scan",
                    "status": "skipped",
                    "applied_at": datetime.now().isoformat(),
                    "match_score": score,
                    "error": eval_result.get("reasoning", "Below threshold"),
                })
                _save_applications(apps)
                skipped += 1
                continue

            # Step 4: Generate cover letter
            cover_letter = ""
            if settings.job_hunter.cover_letter_enabled:
                cl_result = await cover_gen.execute(
                    job_title=title, company=job.get("company", ""), job_description=desc,
                )
                cover_letter = cl_result.get("cover_letter", "")

            # Step 5: Fill + Submit (attempt)
            filler = FillApplicationTool()
            fill_result = await filler.execute(url=url, cover_letter=cover_letter)

            if fill_result.get("status") == "success":
                submitter = SubmitApplicationTool()
                sub_result = await submitter.execute(
                    job_title=title, company=job.get("company", ""),
                    job_url=url, source="scan", cover_letter=cover_letter,
                    match_score=score,
                )
                if sub_result.get("status") == "success":
                    applied += 1
                else:
                    failed += 1
            else:
                failed += 1

        return {
            "status": "success",
            "message": f"Scan complete! Applied to {applied} jobs, skipped {skipped}, failed {failed}",
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "total_found": len(jobs),
            "new_jobs": len(new_jobs),
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class JobHunterAgent(BaseAgent):
    """Autonomously searches for and applies to jobs — your personal AI recruiter."""

    name = "job_hunter"
    description = "Searches for jobs, evaluates fit, generates cover letters, and auto-applies"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are an expert recruiter and job application assistant. You help the user find and apply to jobs autonomously.\n\n"
        "Your workflow for a job scan:\n"
        "1. Use search_jobs to find relevant positions matching the user's preferences\n"
        "2. Use read_job_posting to get full job descriptions\n"
        "3. Use evaluate_job_fit to score each job against the user's profile\n"
        "4. For good matches, use generate_cover_letter to create a tailored letter\n"
        "5. Use fill_application to auto-fill the application form from the profile\n"
        "6. Use upload_resume to attach the resume\n"
        "7. Use submit_application to submit and log the result\n\n"
        "For quick overviews, use check_application_status to show past applications.\n"
        "Use update_profile to keep the user's info current.\n"
        "Use set_preferences to adjust search criteria.\n"
        "Use run_job_scan for a fully automated search → evaluate → apply cycle.\n\n"
        "Always report what you did: how many jobs found, applied, skipped, and any failures."
    )

    offline_responses = {
        "job": "🔍 I can search for jobs for you! Connect an LLM and I'll find matching positions!",
        "apply": "📝 I can apply to jobs automatically! Set up your profile and preferences first.",
        "resume": "📄 I can help with your resume and applications!",
        "career": "💼 I'm your career assistant! I can search, evaluate, and apply to jobs for you.",
        "application": "📋 I can check your application status or submit new applications!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            SearchJobsTool(),
            BrowseJobBoardTool(),
            ReadJobPostingTool(),
            EvaluateJobFitTool(),
            GenerateCoverLetterTool(),
            FillApplicationTool(),
            UploadResumeTool(),
            SubmitApplicationTool(),
            CheckApplicationStatusTool(),
            UpdateProfileTool(),
            SetPreferencesTool(),
            RunJobScanTool(),
        ]
