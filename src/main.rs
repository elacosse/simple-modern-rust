use clap::Parser;

#[derive(Parser)]
#[command(version, about)]
struct Args {
    /// Name to greet.
    #[arg(default_value = "world")]
    name: String,
}

fn main() {
    let args = Args::parse();
    println!("{}", simple_modern_rust::greet(&args.name));
}
