import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SUPPORTED_FORMATS = ("tweet", "instagram", "audio")


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clamp(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


@dataclass(frozen=True)
class Persona:
    name: str
    handle: str
    category: str
    avatar_initials: str
    avatar_color: str
    style_description: str
    real_posts: list[dict[str, Any]]


def _parse_personas(config: dict[str, Any]) -> list[Persona]:
    personas = []
    for p in config.get("personas", []):
        personas.append(
            Persona(
                name=p["name"],
                handle=p["handle"],
                category=p["category"],
                avatar_initials=p["avatar_initials"],
                avatar_color=p["avatar_color"],
                style_description=p["style_description"],
                real_posts=p.get("real_posts", []),
            )
        )
    return personas


def _validate_personas(personas: list[Persona]) -> None:
    if len(personas) != 12:
        raise SystemExit(f"Expected 12 personas, got {len(personas)}")
    seen = set()
    for p in personas:
        key = (p.name, p.category)
        if key in seen:
            raise SystemExit(f"Duplicate persona: {p.name} ({p.category})")
        seen.add(key)
        if p.category not in ("sports", "politics", "celebrity"):
            raise SystemExit(f"Invalid category for {p.name}: {p.category}")
        if len(p.real_posts) != 15:
            raise SystemExit(f"{p.name}: expected 15 real_posts, got {len(p.real_posts)}")
        for i, post in enumerate(p.real_posts, start=1):
            fmt = post.get("format")
            if fmt not in SUPPORTED_FORMATS:
                raise SystemExit(f"{p.name} real_posts[{i}] invalid format: {fmt}")
            if not (post.get("content") or "").strip():
                raise SystemExit(f"{p.name} real_posts[{i}] missing content")
            if not (post.get("source_date") or "").strip():
                raise SystemExit(f"{p.name} real_posts[{i}] missing source_date")


def _question_row(
    *,
    category: str,
    fmt: str,
    persona: str,
    handle: str,
    content: str,
    is_real: bool,
    source_date: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "format": fmt,
        "persona": persona,
        "handle": handle,
        "content": content,
        "is_real": is_real,
        "source_date": source_date,
        "explanation": "" if is_real else "AI-generated imitation for gameplay. Not a real post.",
        "is_approved": True,
        "scheduled_date": None,
        "created_at": created_at,
    }


def _http_post_json(url: str, payload: dict[str, Any], timeout_s: int = 60) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    with urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_text_from_gemini(resp: dict[str, Any]) -> str:
    try:
        parts = resp["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except Exception:
        return ""


def _generate_fake_posts_gemini(
    *,
    api_key: str,
    model: str,
    persona: Persona,
    n: int,
    seed: int | None,
    temperature: float,
) -> list[dict[str, str]]:
    """
    Returns list of {content, format} objects.
    """
    example_snippets = "\n".join(
        f"- ({rp['format']}) {rp['content']}" for rp in random.sample(persona.real_posts, k=min(6, len(persona.real_posts)))
    )

    prompt = f"""
You are generating plausible SOCIAL MEDIA posts for a guessing game (real vs AI).

Persona:
- name: {persona.name}
- handle: {persona.handle}
- category: {persona.category}
- style: {persona.style_description}

Use these as style examples (do NOT copy verbatim):
{example_snippets}

Task:
Generate EXACTLY {n} new posts that feel like {persona.name}'s voice and style, but are entirely fictional.

Constraints:
- Output MUST be valid JSON only (no markdown), a JSON array of objects.
- Each object MUST have: "content" (string), "format" (one of: "tweet", "instagram", "audio").
- Keep each content under 280 characters if format is "tweet".
- For "instagram", write like a caption (may include 1-3 short hashtags).
- For "audio", write like a short spoken transcript (1-2 sentences).
- Avoid defamation, slurs, or explicit sexual content.
- Avoid mentioning that it is AI-generated.
""".strip()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }
    if seed is not None:
        payload["generationConfig"]["seed"] = seed

    # basic retry loop
    last_err = None
    for attempt in range(1, 6):
        try:
            resp = _http_post_json(url, payload, timeout_s=90)
            text = _extract_text_from_gemini(resp).strip()
            data = json.loads(text)
            if not isinstance(data, list) or len(data) != n:
                raise ValueError(f"Unexpected JSON shape/length: {type(data)} len={getattr(data, '__len__', lambda: 'na')()}")
            cleaned: list[dict[str, str]] = []
            for obj in data:
                fmt = str(obj.get("format", "")).strip().lower()
                content = str(obj.get("content", "")).strip()
                if fmt not in SUPPORTED_FORMATS:
                    fmt = "tweet"
                content = _clamp(content, 420 if fmt != "tweet" else 280)
                if not content:
                    continue
                cleaned.append({"format": fmt, "content": content})
            if len(cleaned) != n:
                raise ValueError(f"Got {len(cleaned)} valid posts, expected {n}")
            return cleaned
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            last_err = e
            sleep_s = min(20, 2 ** (attempt - 1))
            print(f"  Gemini call failed (attempt {attempt}/5): {e}. Retrying in {sleep_s}s...", file=sys.stderr)
            time.sleep(sleep_s)
    raise SystemExit(f"Gemini generation failed for {persona.name}: {last_err}")


def build_questions(
    personas: list[Persona],
    *,
    fake_per_persona: int,
    api_key: str | None,
    model: str,
    seed: int | None,
    temperature: float,
) -> list[dict[str, Any]]:
    created_at = _utc_now_iso_z()
    questions: list[dict[str, Any]] = []

    # 1) Real posts
    print("Seeding REAL posts...")
    for p in personas:
        for rp in p.real_posts:
            questions.append(
                _question_row(
                    category=p.category,
                    fmt=rp["format"],
                    persona=p.name,
                    handle=p.handle,
                    content=rp["content"],
                    is_real=True,
                    source_date=rp["source_date"],
                    created_at=created_at,
                )
            )
    print(f"  Added {len(questions)} real questions.")

    # 2) Fake posts (Gemini)
    if api_key:
        print("Generating FAKE posts with Gemini...")
        for idx, p in enumerate(personas, start=1):
            print(f"- [{idx}/{len(personas)}] {p.name}: generating {fake_per_persona} fake posts...")
            fakes = _generate_fake_posts_gemini(
                api_key=api_key,
                model=model,
                persona=p,
                n=fake_per_persona,
                seed=seed,
                temperature=temperature,
            )
            for fp in fakes:
                questions.append(
                    _question_row(
                        category=p.category,
                        fmt=fp["format"],
                        persona=p.name,
                        handle=p.handle,
                        content=fp["content"],
                        is_real=False,
                        source_date="generated",
                        created_at=created_at,
                    )
                )
        print(f"  Added {fake_per_persona * len(personas)} fake questions.")
    else:
        print("Skipping Gemini generation (GEMINI_API_KEY not set).", file=sys.stderr)

    # Assign deterministic ids for convenience (DB can still autoincrement)
    for i, q in enumerate(questions, start=1):
        q["id"] = i

    random.shuffle(questions)
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed questions.json from personas.json using Gemini.")
    parser.add_argument("--config", required=True, help="Path to personas.json")
    parser.add_argument("--output", required=True, help="Output path for questions.json")
    parser.add_argument("--fake-per-persona", type=int, default=15, help="Number of fake posts to generate per persona")
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"), help="Gemini model name")
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed passed to Gemini (if supported)")
    parser.add_argument("--temperature", type=float, default=0.9, help="Gemini sampling temperature")
    args = parser.parse_args()

    config_path = Path(args.config)
    output_path = Path(args.output)

    config = _read_json(config_path)
    personas = _parse_personas(config)
    _validate_personas(personas)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Only real posts will be written.", file=sys.stderr)

    # Make output deterministic-ish across runs (ordering) even if model is random
    random.seed(42)

    questions = build_questions(
        personas,
        fake_per_persona=args.fake_per_persona,
        api_key=api_key,
        model=args.model,
        seed=args.seed,
        temperature=args.temperature,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, questions)
    print(f"Done. Wrote {len(questions)} questions to {output_path}")


if __name__ == "__main__":
    main()

