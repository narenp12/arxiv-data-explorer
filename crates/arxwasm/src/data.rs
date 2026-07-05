use serde::Deserialize;

#[derive(Clone, Debug)]
pub struct Author {
    pub name: String,
    pub weight: u32,
    pub coauthors: Vec<String>,
    pub rank: Option<u32>,
}

#[derive(Clone, Debug, Default)]
pub struct AuthorStore {
    pub authors: Vec<Author>,
}

#[derive(Deserialize)]
struct RawShardEntry {
    w: u32,
    co: Vec<[String; 2]>,
}

type RawShard = std::collections::HashMap<String, RawShardEntry>;

impl AuthorStore {
    pub fn from_shards(shards_json: &str, rankings_json: &str) -> Self {
        let shard: RawShard = serde_json::from_str(shards_json).expect("valid shard JSON");
        let mut store = AuthorStore::default();

        for (name, entry) in shard {
            store.authors.push(Author {
                name: name.clone(),
                weight: entry.w,
                coauthors: entry.co.iter().map(|c| c[0].clone()).collect(),
                rank: None,
            });
        }

        if let Ok(rankings) = serde_json::from_str::<Vec<serde_json::Value>>(rankings_json) {
            let name_to_rank: std::collections::HashMap<&str, u32> = rankings
                .iter()
                .enumerate()
                .map(|(i, v)| (v["name"].as_str().unwrap_or(""), i as u32))
                .collect();
            for author in &mut store.authors {
                author.rank = name_to_rank.get(author.name.as_str()).copied();
            }
        }

        store
    }
}
