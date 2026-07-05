import re


def strip_latex(text: str) -> str:
    if not text:
        return ""

    t = text

    # display math $$...$$ and \[...\]
    t = re.sub(r"\$\$[^$]*\$\$", "", t)
    t = re.sub(r"\\\[[^\]]*\\\]", "", t)
    # environment start/end markers (keep content between them)
    t = re.sub(r"\\begin\{[^}]*\}", "", t)
    t = re.sub(r"\\end\{[^}]*\}", "", t)
    # inline math $...$
    t = re.sub(r"\$[^$]*?\$", "", t)
    # citation/reference commands → drop entirely
    t = re.sub(
        r"\\(?:cite|ref|label|pageref|eqref|autoref|footnote)\{[^}]*\}", "", t
    )
    # formatting \command{content} → keep content
    t = re.sub(
        r"\\(?:text|mathbf|mathit|mathrm|mathcal|mathbb|mathfrak|mathsf|mathtt|"
        r"textbf|textit|textrm|emph|"
        r"displaystyle|textstyle|scriptstyle|footnotesize|small|normalsize|"
        r"large|Large|LARGE|huge|Huge|"
        r"mbox|url)\{([^}]*)\}",
        r"\1",
        t,
    )
    # remaining \commands → drop
    t = re.sub(r"\\(?:[a-zA-Z]+|.)", "", t)
    # special chars
    t = re.sub(r"[{}~^_#&]", "", t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    return t
