use arxcheck::{Check, Severity, checks};
use clap::Parser;
use std::process;

#[derive(Parser)]
#[command(
    name = "arxcheck",
    about = "Validate arxiv-data-explorer JSON data files"
)]
struct Args {
    /// Path to static/data directory
    #[arg(default_value = "static/data")]
    data_dir: String,

    /// Only run specific check (shard, edges, graph, xref)
    #[arg(long)]
    check: Option<String>,
}

fn main() {
    let args = Args::parse();

    let violations = if let Some(name) = &args.check {
        match name.as_str() {
            "shard" => checks::shard::ShardCheck.run(&args.data_dir),
            "edges" => checks::edges::EdgesCheck.run(&args.data_dir),
            "graph" => checks::graph::GraphCheck.run(&args.data_dir),
            "xref" => checks::xref::CrossRefCheck.run(&args.data_dir),
            _ => {
                eprintln!("Unknown check: {name}. Available: shard, edges, graph, xref");
                process::exit(2);
            }
        }
    } else {
        checks::run_all(&args.data_dir)
    };

    if violations.is_empty() {
        println!("✓ All checks passed");
        process::exit(0);
    }

    let errors: Vec<_> = violations
        .iter()
        .filter(|v| v.severity == Severity::Error)
        .collect();
    let warnings: Vec<_> = violations
        .iter()
        .filter(|v| v.severity == Severity::Warning)
        .collect();

    if !errors.is_empty() {
        eprintln!("\nErrors ({}):", errors.len());
        for v in &errors {
            eprintln!("  [{}] {}", v.file, v.message);
        }
    }
    if !warnings.is_empty() {
        eprintln!("\nWarnings ({}):", warnings.len());
        for v in &warnings {
            eprintln!("  [{}] {}", v.file, v.message);
        }
    }

    let has_errors = !errors.is_empty();
    if has_errors {
        process::exit(1);
    }
}
