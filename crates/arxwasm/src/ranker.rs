use crate::data::Author;

/// Score candidates: exact prefix > fuzzy; within tier, weight × co-count × rank.
pub fn rank_candidates(authors: &[Author], indices: &[usize], query: &str) -> Vec<usize> {
    let query_lower = query.to_ascii_lowercase();

    let tier_score = |author: &Author| -> f64 {
        author.weight as f64 * (1.0 + author.coauthors.len() as f64)
    };

    let mut exact: Vec<usize> = Vec::new();
    let mut fuzzy: Vec<usize> = Vec::new();

    for &idx in indices {
        let name_lower = authors[idx].name.to_ascii_lowercase();
        if name_lower.starts_with(&query_lower) {
            exact.push(idx);
        } else {
            fuzzy.push(idx);
        }
    }

    exact.sort_by(|&a, &b| {
        tier_score(&authors[b])
            .partial_cmp(&tier_score(&authors[a]))
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    fuzzy.sort_by(|&a, &b| {
        tier_score(&authors[b])
            .partial_cmp(&tier_score(&authors[a]))
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    exact.into_iter().chain(fuzzy).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::Author;

    fn make_author(name: &str, weight: u32, co_count: u32) -> Author {
        Author {
            name: name.to_string(),
            weight,
            coauthors: (0..co_count).map(|i| format!("co{i}")).collect(),
            rank: None,
        }
    }

    #[test]
    fn exact_prefix_ranks_higher() {
        let authors = vec![
            make_author("Wei Wang", 100, 0),
            make_author("C. Chen", 200, 5),
        ];
        let r = rank_candidates(&authors, &[0, 1], "wei");
        assert_eq!(r[0], 0);
    }

    #[test]
    fn higher_weight_ranks_higher_within_tier() {
        let authors = vec![
            make_author("C. Chen", 50, 0),
            make_author("Chao Chen", 200, 0),
        ];
        let r = rank_candidates(&authors, &[0, 1], "chen");
        assert_eq!(r[0], 1);
    }
}
