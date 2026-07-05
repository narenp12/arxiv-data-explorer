use std::collections::HashMap;

#[derive(Default)]
struct TrieNode {
    children: HashMap<char, TrieNode>,
    author_indices: Vec<usize>,
}

#[derive(Default)]
pub struct AuthorTrie {
    root: TrieNode,
}

impl AuthorTrie {
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert a normalized author name linked to its index in AuthorStore.
    pub fn insert(&mut self, normalized: &str, author_idx: usize) {
        let mut node = &mut self.root;
        for ch in normalized.chars() {
            node = node.children.entry(ch).or_default();
        }
        node.author_indices.push(author_idx);
    }

    /// Find all author indices whose normalized name starts with `prefix`.
    pub fn search(&self, prefix: &str) -> Vec<usize> {
        let mut node = &self.root;
        for ch in prefix.chars() {
            match node.children.get(&ch) {
                Some(child) => node = child,
                None => return Vec::new(),
            }
        }
        let mut results = Vec::new();
        collect_all(&node, &mut results);
        results
    }
}

fn collect_all(node: &TrieNode, out: &mut Vec<usize>) {
    out.extend_from_slice(&node.author_indices);
    for child in node.children.values() {
        collect_all(child, out);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_prefix_match() {
        let mut trie = AuthorTrie::new();
        trie.insert("c chen", 0);
        trie.insert("wei wang", 1);
        let r = trie.search("c chen");
        assert_eq!(r, vec![0]);
    }

    #[test]
    fn prefix_returns_multiple() {
        let mut trie = AuthorTrie::new();
        trie.insert("wei", 0);
        trie.insert("wei wang", 1);
        trie.insert("wei zhang", 2);
        let r = trie.search("wei");
        assert_eq!(r.len(), 3);
    }

    #[test]
    fn no_match_returns_empty() {
        let trie = AuthorTrie::new();
        let r = trie.search("nonexistent");
        assert!(r.is_empty());
    }
}
