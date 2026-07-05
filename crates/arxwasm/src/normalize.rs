/// Strip punctuation, lowercase, normalize Unicode.
pub fn normalize(name: &str) -> String {
    name.chars()
        .map(|c| match c {
            c if c.is_ascii_alphanumeric() || c.is_whitespace() => c.to_ascii_lowercase(),
            '.' | ',' | '-' | '\'' | '(' | ')' => ' ',
            _ => c.to_ascii_lowercase(),
        })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

/// Normalize a search query — same as normalize but trims aggressively.
pub fn normalize_for_search(query: &str) -> String {
    normalize(query.trim())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_punctuation() {
        assert_eq!(normalize("C. Chen"), "c chen");
    }

    #[test]
    fn lowercases() {
        assert_eq!(normalize("Wei Wang"), "wei wang");
    }

    #[test]
    fn collapses_whitespace() {
        assert_eq!(normalize("  Zhang   Wei  "), "zhang wei");
    }
}
