def format_value(value) -> str:
    """Format missing values, booleans, and other values."""
    if value is None:
        return "Não informado"
    if value is True:
        return "Sim"
    if value is False:
        return "Não"
    return str(value)


def format_money(value) -> str:
    """Format a numeric amount as Brazilian currency."""
    if value is None:
        return "Não informado"

    if type(value) not in (int, float):
        return str(value)

    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",")
    return "R$ " + formatted.replace("_", ".")


def build_report(
    analysis: dict,
    filtered_result: dict,
) -> str:
    """Report all extracted positions and their filtering outcome."""
    positions = analysis["positions"]
    remaining = filtered_result["positions"]

    lines = [
        "# Relatório de oportunidades",
        "",
        "## Resumo",
        "",
        f"- **Órgão:** {format_value(analysis.get('organization'))}",
        "- **Notícias analisadas:** 1",
        f"- **Registros de cargos/localidades:** {len(positions)}",
        f"- **Mantidos após o filtro:** {len(remaining)}",
        f"- **Excluídos pelo filtro:** {len(positions) - len(remaining)}",
        "",
        f"**Notícia consultada:** {analysis['source_url']}",
        "",
        "Os números acima contam registros, não o total de vagas ofertadas.",
        "Foi aplicado somente o filtro de contratação temporária.",
        "",
        "## Detalhes dos registros analisados",
        "",
    ]

    if not positions:
        lines.extend([
            "A IA não identificou posições relacionadas à Farmácia "
            "nesta notícia.",
            "",
        ])

    for index, position in enumerate(positions, start=1):
        title = format_value(position.get("title"))
        kept = position in remaining

        lines.extend([
            f"### {index}. {title}",
            "",
        ])

        if kept:
            lines.append(
                "**Resultado do filtro:** mantido para conferência."
            )

            if position.get("temporary") is None:
                lines.append(
                    "**Atenção:** a natureza temporária da contratação "
                    "não foi determinada."
                )
        else:
            lines.extend([
                "**Resultado do filtro:** excluído.",
                "**Motivo:** contratação identificada como temporária, "
                "excluída pelas preferências configuradas.",
            ])

        lines.append("")

        fields = [
            ("city", "Município"),
            ("state", "Estado"),
            ("vacancies", "Vagas informadas para este cargo/localidade"),
            ("reserve_list", "Cadastro de reserva"),
            ("temporary", "Contratação temporária"),
            ("weekly_hours", "Carga horária semanal"),
            ("requirements", "Requisitos"),
            ("registration_start", "Início das inscrições"),
            ("registration_end", "Fim das inscrições"),
            ("exam_date", "Data da prova extraída da notícia"),
        ]

        for key, label in fields:
            lines.append(
                f"- **{label}:** {format_value(position.get(key))}"
            )

        lines.extend([
            f"- **Remuneração:** {format_money(position.get('salary_brl'))}",
            "- **Taxa de inscrição:** "
            f"{format_money(position.get('application_fee_brl'))}",
            "",
            "**Trecho de evidência retornado pela IA:**",
            "",
            format_value(position.get("evidence")),
            "",
        ])

    lines.extend([
        "## Observações retornadas pela IA",
        "",
    ])

    warnings = analysis.get("warnings", [])

    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append(
            "A IA não retornou observações. Isso não confirma "
            "que os dados estejam completos."
        )

    lines.extend([
        "",
        "## Conferências pendentes",
        "",
        "- Confirmar os dados no edital oficial e nas retificações.",
        "- Verificar os requisitos específicos de formação e habilitação.",
        "- Confirmar se as inscrições estão abertas.",
        "- Conferir se a data da prova é definitiva ou apenas prevista.",
        "- Aplicar os demais filtros, incluindo região.",
        "",
        "Este relatório cobre somente uma notícia. "
        "As demais oportunidades coletadas ainda não foram analisadas.",
        "",
    ])

    return "\n".join(lines)

def build_batch_report(results: list[dict], pending: list[dict]) -> str:
    """Combine article reports and list processing issues."""
    lines = [
        "# Relatório do lote",
        "",
        f"- Notícias com análise disponível: {len(results)}",
        f"- Notícias pendentes ou com erro: {len(pending)}",
        "",
        "Cada seção abaixo corresponde a uma notícia.",
        "Somente o filtro de contratação temporária foi aplicado.",
        "",
    ]

    for index, result in enumerate(results, start=1):
        article_report = build_report(
            result["analysis"],
            result["filtered_result"],
        )

        # Nest each individual report under the batch report.
        nested_report = "\n".join(
            "#" + line if line.startswith("#") else line
            for line in article_report.splitlines()
        )

        lines.extend([
            "---",
            "",
            f"Notícia {index}",
            "",
            nested_report,
        ])

    if pending:
        lines.extend([
            "## Notícias pendentes ou com erro",
            "",
        ])

        for item in pending:
            lines.extend([
                f"- **Notícia:** {item['title']}",
                f"  - Link: {item['url']}",
                f"  - Motivo: {item['reason']}",
                "",
            ])

    return "\n".join(lines)