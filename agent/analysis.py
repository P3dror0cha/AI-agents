import json

from openai import OpenAI


def analyze_article(
    article_text: str,
    instructions: str,
    client: OpenAI,
    model: str,
) -> dict:
    """Extract recruitment information from an article using AI."""
    if not article_text.strip():
        raise ValueError("The article text is empty.")

    if not instructions.strip():
        raise ValueError("The analysis instructions are empty.")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": article_text},
        ],
        response_format={"type": "json_object"},
        reasoning_effort="low",
        max_completion_tokens=3000,
    )

    choice = response.choices[0]

    if choice.finish_reason != "stop":
        raise ValueError(
            f"The analysis did not finish normally: {choice.finish_reason}"
        )

    content = choice.message.content

    if not content:
        raise ValueError("The model returned no text.")

    result = json.loads(content)

    if not isinstance(result, dict):
        raise ValueError("The analysis must be a JSON object.")

    if not isinstance(result.get("positions"), list):
        raise ValueError("The analysis must contain a positions list.")

    if not all(isinstance(item, dict) for item in result["positions"]):
        raise ValueError("Each position must be a JSON object.")

    if not isinstance(result.get("warnings"), list):
        raise ValueError("The analysis must contain a warnings list.")

    # Validate employment type before returning the analysis.
    for position in result["positions"]:
        if "temporary" not in position:
            raise ValueError("A position is missing the temporary field.")

        temporary = position["temporary"]

        if temporary is not None and type(temporary) is not bool:
            raise ValueError(
                "The temporary field must be true, false, or null."
            )

    return result


def filter_positions(
    positions: list[dict],
    include_temporary_positions: bool,
) -> list[dict]:
    """Exclude confirmed temporary positions when requested."""
    if type(include_temporary_positions) is not bool:
        raise ValueError(
            "include_temporary_positions must be a boolean."
        )

    if include_temporary_positions:
        return positions.copy()

    return [
        position
        for position in positions
        if position["temporary"] is not True
    ]