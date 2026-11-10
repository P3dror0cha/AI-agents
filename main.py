import json
import os
import time
from pathlib import Path
from urllib.error import URLError

from dotenv import load_dotenv
from openai import OpenAI, APIError

from agent.analysis import analyze_article, filter_positions
from agent.collection import (
    fetch_page,
    extract_opportunities,
    extract_article_text,
)
from agent.configuration import load_config
from agent.report import build_batch_report
from agent.storage import (
    initialize_database,
    create_cache_key,
    load_analysis,
    save_analysis,
)


def main():
    """Process a limited batch and reuse saved analyses."""
    project_dir = Path(__file__).resolve().parent
    config = load_config(project_dir / "config.yaml")
    load_dotenv(project_dir / ".env")

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing.")

    processing = config["processing"]
    max_articles = processing["max_articles"]
    max_new_analyses = processing["max_new_analyses"]
    delay = processing["request_delay_seconds"]

    if type(max_articles) is not int or max_articles < 1:
        raise ValueError("max_articles must be a positive integer.")

    if type(max_new_analyses) is not int or max_new_analyses < 0:
        raise ValueError("max_new_analyses must be a non-negative integer.")

    if type(delay) not in (int, float) or delay < 0:
        raise ValueError("request_delay_seconds must be non-negative.")

    output_dir = project_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    database_path = project_dir / config["storage"]["database_path"]
    initialize_database(database_path)

    instructions = (
        project_dir / "prompts/analyze_competition.txt"
    ).read_text(encoding="utf-8")

    if not instructions.strip():
        raise ValueError("The analysis instructions are empty.")

    client = OpenAI(
        api_key=api_key,
        base_url=config["ai"]["base_url"],
        timeout=60.0,
        max_retries=0,
    )

    source = config["sources"]["pci"]

    print("Fetching the opportunity listing...")

    html = fetch_page(
        source["url"],
        source["timeout_seconds"],
    )

    (output_dir / "pci_page.html").write_text(
        html, encoding="utf-8"
    )

    opportunities = extract_opportunities(html, source["url"])
    print(f"Opportunities found: {len(opportunities)}")

    if not opportunities:
        raise ValueError(
            "No matching links found. Inspect the downloaded listing."
        )

    selected = opportunities[:max_articles]

    results = []
    pending = []
    api_requests = 0
    reused_analyses = 0
    api_available = True

    for index, opportunity in enumerate(selected, start=1):
        print(f"\n[{index}/{len(selected)}] {opportunity['title']}")

        # Pause before article downloads.
        time.sleep(delay)

        try:
            article_html = fetch_page(
                opportunity["url"],
                source["timeout_seconds"],
            )
            article_text = extract_article_text(article_html)
        except (URLError, TimeoutError, UnicodeError, ValueError) as error:
            pending.append({
                **opportunity,
                "reason": f"Falha na coleta ou extração: {error}",
            })
            print("Collection failed. Continuing to the next article.")
            continue

        cache_key = create_cache_key(
            source_url=opportunity["url"],
            article_text=article_text,
            instructions=instructions,
            provider=config["ai"]["provider"],
            model=config["ai"]["model"],
        )

        # Keep separate source files for each analysis input.
        article_dir = output_dir / "articles" / cache_key
        article_dir.mkdir(parents=True, exist_ok=True)

        (article_dir / "article.html").write_text(
            article_html, encoding="utf-8"
        )
        (article_dir / "article.txt").write_text(
            article_text, encoding="utf-8"
        )

        analysis = load_analysis(database_path, cache_key)

        if analysis is not None:
            reused_analyses += 1
            print("Using saved analysis. No AI request needed.")
        else:
            if not api_available or api_requests >= max_new_analyses:
                reason = (
                    "Novas chamadas suspensas após erro da API."
                    if not api_available
                    else "Limite de novas análises desta execução atingido."
                )
                pending.append({**opportunity, "reason": reason})
                print("Article pending. No AI request made.")
                continue

            # Count attempts, including unsuccessful requests.
            api_requests += 1
            print("Analyzing with Groq...")

            try:
                analysis = analyze_article(
                    article_text=article_text,
                    instructions=instructions,
                    client=client,
                    model=config["ai"]["model"],
                )
            except APIError as error:
                api_available = False
                pending.append({
                    **opportunity,
                    "reason": f"Falha na API: {type(error).__name__}",
                })
                print(
                    f"API error: {type(error).__name__}. "
                    "Further API calls are suspended for this run."
                )
                continue
            except ValueError as error:
                pending.append({
                    **opportunity,
                    "reason": f"Resposta da IA rejeitada: {error}",
                })
                print(f"Invalid analysis: {error}")
                continue

            analysis["source_url"] = opportunity["url"]

            save_analysis(
                database_path,
                cache_key,
                opportunity["url"],
                analysis,
            )
            print("Analysis saved to the database.")

        analysis["source_url"] = opportunity["url"]

        filtered_positions = filter_positions(
            analysis["positions"],
            config["search"]["include_temporary_positions"],
        )

        filtered_result = {
            "organization": analysis.get("organization"),
            "source_url": opportunity["url"],
            "positions": filtered_positions,
            "warnings": analysis["warnings"],
        }

        result = {
            "analysis": analysis,
            "filtered_result": filtered_result,
        }
        results.append(result)

        (article_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    batch = {
        "selected_articles": len(selected),
        "api_requests": api_requests,
        "reused_analyses": reused_analyses,
        "results": results,
        "pending": pending,
    }

    (output_dir / "batch_results.json").write_text(
        json.dumps(batch, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_path = project_dir / config["report"]["output_path"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_batch_report(results, pending),
        encoding="utf-8",
    )

    print(f"\nArticles with results: {len(results)}")
    print(f"Reused analyses: {reused_analyses}")
    print(f"New API requests: {api_requests}")
    print(f"Pending articles: {len(pending)}")
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()