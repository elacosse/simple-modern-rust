use std::process::Command;

fn run(args: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_simple-modern-rust"))
        .args(args)
        .output()
        .expect("run CLI")
}

#[test]
fn greets_and_reports_metadata() {
    let output = run(&["Ada"]);
    assert!(output.status.success());
    assert_eq!(output.stdout, b"Hello, Ada!\n");
    assert!(output.stderr.is_empty());
    let help = run(&["--help"]);
    assert!(help.status.success());
    assert!(String::from_utf8_lossy(&help.stdout).contains(env!("CARGO_PKG_DESCRIPTION")));
    let version = run(&["--version"]);
    assert!(version.status.success());
    assert!(String::from_utf8_lossy(&version.stdout).contains(env!("CARGO_PKG_VERSION")));
}

#[test]
fn invalid_arguments_fail_on_stderr() {
    let output = run(&["--not-an-option"]);
    assert!(!output.status.success());
    assert!(output.stdout.is_empty());
    assert!(!output.stderr.is_empty());
}
