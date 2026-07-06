use std::collections::HashMap;

fn trigrams(s: &str) -> Vec<String> {
    let padded = format!("  {s} ");
    padded
        .chars()
        .collect::<Vec<_>>()
        .windows(3)
        .map(|w| w.iter().collect())
        .collect()
}

#[derive(Default)]
pub struct TrigramIndex {
    posting: HashMap<String, Vec<(usize, u32)>>,
}

impl TrigramIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&mut self, normalized: &str, author_idx: usize) {
        let grams = trigrams(normalized);
        let total = grams.len() as u32;
        for g in &grams {
            self.posting.entry(g.clone()).or_default().push((author_idx, total));
        }
    }

    /// Returns (author_idx, similarity) sorted by similarity descending.
    pub fn search(&self, query: &str) -> Vec<(usize, f64)> {
        let qgrams = trigrams(query);
        if qgrams.is_empty() {
            return Vec::new();
        }
        let qtotal = qgrams.len() as f64;

        let mut scores: HashMap<usize, (u32, u32)> = HashMap::new();
        for g in &qgrams {
            if let Some(entries) = self.posting.get(g) {
                for &(idx, doctotal) in entries {
                    let entry = scores.entry(idx).or_insert((0, doctotal));
                    entry.0 += 1;
                }
            }
        }

        let mut results: Vec<(usize, f64)> = scores
            .into_iter()
            .map(|(idx, (matches, doctotal))| {
                let sim = 2.0 * matches as f64 / (qtotal + doctotal as f64);
                (idx, sim)
            })
            .filter(|(_, sim)| *sim > 0.3)
            .collect();
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        results.truncate(20);
        results
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trigram_generation() {
        let grams = trigrams("chen");
        assert!(grams.contains(&"  c".to_string()));
        assert!(grams.contains(&"hen".to_string()));
    }

    #[test]
    fn fuzzy_match() {
        let mut idx = TrigramIndex::new();
        idx.insert("chen", 0);
        let r = idx.search("chn");
        assert!(!r.is_empty());
        assert_eq!(r[0].0, 0);
    }

    #[test]
    fn no_match() {
        let idx = TrigramIndex::new();
        let r = idx.search("xyzabc");
        assert!(r.is_empty());
    }
}
